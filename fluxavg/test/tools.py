#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan 22 12:53:04 2019

@author: csat8800
"""
import numpy as np
from matplotlib import pyplot as plt
import xarray as xr
xr.set_options(keep_attrs=True)
import os
import pandas as pd
from datetime import datetime
from functools import partial
import socket
print = partial(print, flush=True)

dim_dict = dict(x="U",y="V",bottom_top="W",z="W")
xy = ["x", "y"]
XY = ["X", "Y"]
XYZ = [*XY, "Z"]
uvw = ["u", "v", "w"]
tex_names = {"t" : "\\theta", "q" : "q_\\mathrm{v}"}
units_dict = {"t" : "K ", "q" : "", **{v : "ms$^{-1}$" for v in uvw}}
units_dict_tend = {"t" : "Ks$^{-1}$", "q" : "s$^{-1}$", **{v : "ms$^{-2}$" for v in uvw}}
units_dict_flux = {"t" : "Kms$^{-1}$", "q" : "ms$^{-1}$", **{v : "m$^{2}$s$^{-2}$" for v in uvw}}
units_dict_tend_rho = {"t" : "kg m$^{-3}$Ks$^{-1}$", "q" : "kg m$^{-3}$s$^{-1}$", **{v : "kg m$^{-2}$s$^{-2}$" for v in uvw}}
g = 9.81
rvovrd = 461.6/287.04
stagger_const = ["FNP", "FNM", "CF1", "CF2", "CF3", "CFN", "CFN1"]

#%% figloc
host = socket.gethostname()
basedir = "~/phd/"
basedir = os.path.expanduser(basedir)
figloc = basedir + "figures/"

#%%open dataset
def fix_coords(data, dx, dy):
    """Assign time and space coordinates"""

    #assign time coordinate
    if ("XTIME" in data) and (type(data.XTIME.values[0]) == np.datetime64):
        data = data.assign_coords(Time=data.XTIME)
    else:
        time = data.Times.astype(str).values
        time = pd.DatetimeIndex([datetime.fromisoformat(str(t)) for t in time])
        data = data.assign_coords(Time=time)

    for v in ["XTIME", "Times"]:
        if v in data:
            data = data.drop(v)
    #assign x and y coordinates and rename dimensions
    for dim_old, res, dim_new in zip(["south_north", "west_east"], [dy, dx], ["y", "x"]):
        for stag in [False, True]:
            if stag:
                dim_old = dim_old + "_stag"
                dim_new = dim_new + "_stag"
            if dim_old in data.dims:
                data[dim_old] = np.arange(data.sizes[dim_old]) * res
                data[dim_old] = data[dim_old] - (data[dim_old][-1] + res)/2
                data[dim_old] = data[dim_old].assign_attrs({"units" : "m"})
                data = data.rename({dim_old : dim_new})

    #assign vertical coordinate
    if ("ZNW" in data) and ("bottom_top_stag" in data.dims):
        data = data.assign_coords(bottom_top_stag=data["ZNW"].isel(Time=0,drop=True))
    if ("ZNU" in data) and ("bottom_top" in data.dims):
        data = data.assign_coords(bottom_top=data["ZNU"].isel(Time=0,drop=True))

    return data

def open_dataset(file, var=None, chunks=None, del_attrs=True, fix_c=True, **kwargs):
    try:
        ds = xr.open_dataset(file, **kwargs)
    except ValueError as e:
        if "unable to decode time" in e.args[0]:
            ds = xr.open_dataset(file, decode_times=False, **kwargs)
        else:
            raise e
    if fix_c:
        dx, dy = ds.DX, ds.DY
        ds = fix_coords(ds, dx=dx, dy=dy)

    if var is not None:
        var = make_list(var)
        ds = ds[var]

    if chunks is not None:
        ds = chunk_data(ds, chunks)

    if del_attrs:
        ds.attrs = {}

    return ds

def chunk_data(data, chunks):
    chunks = {d : c for d,c in chunks.items() if d in data.dims}
    return data.chunk(chunks)

#%%misc



def make_list(o):
    if type(o) not in [tuple, list, dict, np.ndarray]:
        o = [o]
    return o


def avg_xy(data, avg_dims):
    """Average data over the given dimensions even
    if the actual present dimension has '_stag' added"""

    avg_dims_final = avg_dims.copy()
    for i,d in enumerate(avg_dims):
        if (d + "_stag" in data.dims):
            avg_dims_final.append(d + "_stag")
            if (d not in data.dims):
                avg_dims_final.remove(d)

    return data.mean(avg_dims_final)

def find_nans(dat):
    """Drop all indeces of each dimension that do not contain NaNs"""
    nans = dat.isnull()
    nans = nans.where(nans)
    nans = dropna_dims(nans)
    dat = dat.loc[nans.indexes]

    return dat

def dropna_dims(dat, dims=None, how="all", **kwargs):
    """
    Consecutively drop NaNs along given dimensions.

    Parameters
    ----------
    dat : xarray dataset or dataarray
        input data.
    dims : iterable, optional
        dimensions to use. The default is None, which takes all dimensions.
    how : str, optional
        drop index if "all" or "any" NaNs occur. The default is "all".
    **kwargs : keyword arguments
        kwargs for dropna.

    Returns
    -------
    dat : xarray dataset or dataarray
        reduced data.

    """

    if dims is None:
        dims = dat.dims
    for d in dims:
        dat = dat.dropna(d, how=how, **kwargs)

    return dat

def max_error_scaled(dat, ref):
    """
    Compute maximum absolute error of input data with respect to reference data
    and scale by range of reference data.

    Parameters
    ----------
    dat : array
        input data.
    ref : array
        reference data.

    Returns
    -------
    float
        maximum scaled error.

    """

    err = abs(dat - ref)
    value_range = ref.max() - ref.min()
    return float(err.max()/value_range)

#%%manipulate datasets

def select_ind(a, axis=0, indeces=0):
    """Select indeces along (possibly multiple) axis"""
    for axis in make_list(axis):
        a = a.take(indices=indeces, axis=axis)
    return a

def stagger_like(data, ref, rename=True, cyclic=None, ignore=None, **stagger_kw):
    """
    Stagger/Destagger all spatial dimensions to be consistent with reference data ref.

    Parameters
    ----------
    data : xarray dataarray or dataset
        input data.
    data : xarray dataarray
        reference data.
    rename : boolean, optional
        add "_stag" to dimension name. The default is True.
    cyclic : dict of all dims or None, optional
        use periodic boundary conditions to fill lateral boundary points. The default is False.
    ignore : list, optional
        dimensions to ignore
    **stagger_kw : dict
        keyword arguments for staggering.

    Returns
    -------
    data : xarray dataarray or dataset
        output data.

    """

    if type(data) == xr.core.dataset.Dataset:
        out = xr.Dataset()
        for v in data.data_vars:
            out[v] = stagger_like(data[v], ref, rename=rename, cyclic=cyclic, ignore=ignore, **stagger_kw)
        return out

    if ignore is None:
        ignore = []

    for d in data.dims:
        if (d.lower() != "time") and (d not in ref.dims) and (d not in ignore):
            if "stag" in d:
                data = destagger(data, d, ref[d[:d.index("_stag")]], rename=rename)
            else:
                if (cyclic is not None) and (d in cyclic):
                    cyc = cyclic[d]
                else:
                    cyc = False
                data = stagger(data, d, ref[d + "_stag"], rename=rename, cyclic=cyc, **stagger_kw)

    return data

def stagger(data, dim, new_coord, FNM=0.5, FNP=0.5, rename=True, cyclic=False, **interp_const):
    """
    Stagger WRF output data in given dimension by averaging neighbouring grid points.

    Parameters
    ----------
    data : xarray dataarray
        input data.
    dim : str
        staggering dimension.
    new_coord : array-like
        new coordinate to assign
    FNM : float or 1D array-like, optional
        upper weights for vertical staggering. The default is 0.5.
    FNP : float or 1D array-like, optional
        lower weights for vertical staggering. The default is 0.5.
    rename : boolean, optional
        add "_stag" to dimension name. The default is True.
    cyclic : bool, optional
        use periodic boundary conditions to fill lateral boundary points. The default is False.
    **interp_const : dict
        vertical extrapolation constants

    Returns
    -------
    data_stag : xarray dataarray
        staggered data.

    """

    if dim == "bottom_top":
        data_stag = data*FNM + data.shift({dim : 1})*FNP
    else:
        data_stag = 0.5*(data + data.roll({dim : 1}, roll_coords=False))

    data_stag = post_stagger(data_stag, dim, new_coord, rename=rename, data=data, cyclic=cyclic, **interp_const)

    return data_stag

def post_stagger(data_stag, dim, new_coord, rename=True, data=None, cyclic=False, **interp_const):
    """
    After staggering: rename dimension, assign new coordinate and fill boundary values.

    Parameters
    ----------
    data_stag : xarray dataarray
        staggered data.
    dim : str
        staggering dimension.
    new_coord : array-like
        new coordinate to assign
    rename : boolean, optional
        add "_stag" to dimension name. The default is True.
    data : xarray dataarray, optional
        unstaggered data for vertical extrapolation.
    cyclic : bool, optional
        use periodic boundary conditions to fill lateral boundary points. The default is False.
    **interp_const : dict
        vertical extrapolation constants
.

    Returns
    -------
    data_stag : xarray dataarray
        staggered data.
    """
    dim_s = dim
    if rename:
        dim_s = dim + "_stag"
        data_stag = data_stag.rename({dim : dim_s})

    data_stag[dim_s] = new_coord[:-1]
    data_stag = data_stag.reindex({dim_s : new_coord})

    c = new_coord

    #fill boundary values
    if dim == "bottom_top":
        if interp_const != {}:
            data_stag[{dim_s: 0}] = interp_const["CF1"]*data[{dim : 0}] + interp_const["CF2"]*data[{dim : 1}] + interp_const["CF3"]*data[{dim : 2}]
            data_stag[{dim_s : -1}] = interp_const["CFN"]*data[{dim : -1}] + interp_const["CFN1"]*data[{dim : -2}]
    elif cyclic:
        #set second boundary point equal to first
        data_stag.loc[{dim_s : c[-1]}] = data_stag.loc[{dim_s : c[0]}]
    else:
        #also set first boundary point to NaN
        data_stag.loc[{dim_s : c[0]}] = np.nan

    return data_stag

def destagger(data, dim, new_coord, rename=True):
    """
    Destagger WRF output data in given dimension by averaging neighbouring grid points.

    Parameters
    ----------
    data : xarray dataarray
        input data.
    dim : str
        destaggering dimension.
    new_coord : array-like
        new coordinate to assign
    rename : boolean, optional
        remove "_stag" from dimension name. The default is True.

    Returns
    -------
    data : xarray dataarray
        destaggered data.

    """

    data = 0.5*(data + data.shift({dim : -1}))
    data = data.sel({dim:data[dim][:-1]})
    new_dim = dim
    if rename:
        new_dim = dim[:dim.index("_stag")]
        data = data.rename({dim : new_dim})

    data[new_dim] = new_coord

    return data

def diff(data, dim, new_coord, rename=True, cyclic=False):
    """
    Calculate first order differences along given dimension and assign new coordinates.

    Parameters
    ----------
    data : xarray dataarray
        input data.
    dim : str
        dimension over which to calculate the finite difference.
    new_coord : array-like
        new coordinate to assign
    rename : boolean, optional
        remove/add "_stag" from dimension name. The default is True.
    cyclic : bool, optional
        if final (differenced) data is staggered: use periodic boundary conditions
        to fill lateral boundary points. The default is False.


    Returns
    -------
    out : xarray dataarray
        calculated differences.

    """

    if (dim in ["bottom_top", "z", "bottom_top_stag", "z_stag", "Time"]) or (not cyclic):
        data_s = data.shift({dim : 1})
    else:
        data_s = data.roll({dim : 1}, roll_coords=False)

    out = data - data_s
    if "_stag" in dim:
        out = out.sel({dim : out[dim][1:]})
        new_dim = dim
        if rename and (dim != "Time"):
            new_dim = dim[:dim.index("_stag")]
            out = out.rename({dim : new_dim})
        out[new_dim] = new_coord
    else:
        out = post_stagger(out, dim, new_coord, rename=rename, cyclic=cyclic)

    return out

def remove_deprecated_dims(ds):
    """Remove dimensions that do not occur in any of the variables of the given dataset"""
    var_dims = []
    for v in ds.data_vars:
        var_dims.extend(ds[v].dims)

    for d in ds.dims:
        if d not in var_dims:
            ds = ds.drop(d)
    return ds
#%% WRF tendencies

def sgs_tendency(dat_mean, VAR, grid, dzdd, cyclic, dim_stag=None, mapfac=None):
    sgs = xr.Dataset()
    sgsflux = xr.Dataset()
    if VAR == "W":
        d3s = "bottom_top"
        d3 = "bottom_top_stag"
        vcoord = grid["ZNW"]
        dn = grid["DN"]
    else:
        d3 = "bottom_top"
        d3s = "bottom_top_stag"
        vcoord = grid["ZNU"]
        dn = grid["DNW"]
    fz = dat_mean["F{}Z_SGS_MEAN".format(VAR)]
    rhoz = stagger_like(dat_mean["RHOD_MEAN"], fz, cyclic=cyclic, **grid[stagger_const])
    sgs["Z"] = -diff(fz*rhoz, d3s, new_coord=vcoord)
    sgs["Z"] = sgs["Z"]/dn/grid["MU_STAG_MEAN"]*(-g)
    for d, v in zip(xy, ["U", "V"]):
        #compute corrections
        du = d.upper()
        if mapfac is None:
            m = 1
        else:
            m = mapfac[du]
        fd = dat_mean["F{}{}_SGS_MEAN".format(VAR, du)]
        sgsflux[du] = fd
        fd = fd*stagger_like(dat_mean["RHOD_MEAN"], fd, cyclic=cyclic, **grid[stagger_const])
        cyc = cyclic[d]
        if d in fd.dims:
            #for momentum variances
            ds = d
            d = ds + "_stag"
            flux8v = stagger(fd, ds, new_coord=sgs[d], cyclic=cyc)
        else:
            ds = d + "_stag"
            flux8v = destagger(fd, ds, new_coord=sgs[d])

        if VAR == "W":
            flux8z = destagger(flux8v, d3, grid["ZNU"])
        else:
            flux8z = stagger(flux8v, d3, grid["ZNW"], **grid[stagger_const])
            flux8z[:,[0,-1]] = 0
        corr_sgs = diff(flux8z, d3s, new_coord=vcoord)/dn
        corr_sgs = corr_sgs*stagger_like(dzdd[du], corr_sgs, cyclic=cyclic)

        dx = grid["D" + du]
        sgs[du] = -diff(fd, ds, new_coord=sgs[d], cyclic=cyc)/dx*m
        if VAR == "W":
            m = mapfac["Y"]
        sgs[du] = sgs[du]/grid["RHOD_STAG_MEAN"] + corr_sgs*m/grid["MU_STAG_MEAN"]*(-g)

    sgsflux["Z"] = fz
    sgs = sgs[XYZ]
    sgs = sgs.to_array("dir")
    if VAR == "W":
        sgs[:,:,[0,-1]] = 0

    return sgs, sgsflux


def adv_tend(dat_mean, VAR, grid, mapfac, cyclic, hor_avg=False, avg_dims=None,
             cartesian=False, force_2nd_adv=False, recalc_w=True, dz_out=False):

    print("Compute resolved tendencies")

    #get appropriate staggered variables, vertical velocity, and flux variables
    var_stag = xr.Dataset()
    fluxnames = ["F{}{}_ADV_MEAN".format(VAR, d) for d in XYZ]
    if force_2nd_adv:
        fluxnames = [fn + "_2ND" for fn in fluxnames]
        for d, f in zip(XYZ, fluxnames):
            var_stag[d] = stagger_like(dat_mean["{}_MEAN".format(VAR)], dat_mean[f], cyclic=cyclic, **grid[stagger_const])
    else:
        for d in XYZ:
            var_stag[d] = dat_mean["{}{}_MEAN".format(VAR, d)]

    if cartesian and (not recalc_w):
        fluxnames[-1] += "_PROG"
        w = dat_mean["W_MEAN"]
    elif cartesian:
        w = dat_mean["WD_MEAN"]
    else:
        rhod = stagger(dat_mean["RHOD_MEAN"], "bottom_top", dat_mean["bottom_top_stag"], **grid[stagger_const])
        w = dat_mean["WW_MEAN"]/(-g*rhod)

    print("fluxes: " + str(fluxnames))
    if not all([f in dat_mean for f in fluxnames]):
        print("Fluxes not available!")
        return

    vmean = xr.Dataset({"X" : dat_mean["U_MEAN"], "Y" : dat_mean["V_MEAN"], "Z" : w})
    if hor_avg:
        var_stag = avg_xy(var_stag, avg_dims)
        for k in vmean.keys():
            vmean[k] = avg_xy(vmean[k], avg_dims)

    tot_flux = dat_mean[fluxnames]
    tot_flux = tot_flux.rename(dict(zip(fluxnames, XYZ)))
    rhod8z = stagger_like(dat_mean["RHOD_MEAN"], tot_flux["Z"], cyclic=cyclic, **grid[stagger_const])

    if dz_out:
        corr = tot_flux[XY]
        corr["T"] = dat_mean[VAR + "_MEAN"]
        corr = rhod8z*stagger_like(corr, rhod8z, cyclic=cyclic, **grid[stagger_const])
    else:
        corr = ["F{}X_CORR".format(VAR), "F{}Y_CORR".format(VAR), "CORR_D{}DT".format(VAR)]
        if force_2nd_adv:
            corr = [corri + "_2ND" for corri in corr]
        corr = dat_mean[corr]
    corr = corr.to_array("dir")
    corr["dir"] = ["X", "Y", "T"]

    if not cartesian:
          tot_flux["Z"] = tot_flux["Z"] - (corr.loc["X"] + corr.loc["Y"] + corr.loc["T"])/rhod8z

  #  mean advective fluxes
    mean_flux = xr.Dataset()
    for d in XYZ:
        if hor_avg and (d.lower() in avg_dims):
            mean_flux[d] = 0.
        else:
            vel_stag = stagger_like(vmean[d], ref=var_stag[d], cyclic=cyclic, **grid[stagger_const])
            var_stag_d = var_stag[d]
            if (VAR == "W") and (d in XY):
                vel_stag[{"bottom_top_stag" : 0}] = 0
            mean_flux[d] = var_stag_d*vel_stag

    #advective tendency from fluxes
    adv = {}
    fluxes = {"adv_r" : tot_flux, "mean" : mean_flux}
    for comp, flux in fluxes.items():
        adv_i = xr.Dataset()
        mf = mapfac
        rhod8z_m = rhod8z
        if (comp == "mean") and hor_avg:
            mf = avg_xy(mapfac, avg_dims)
            rhod8z_m = avg_xy(rhod8z, avg_dims)
        for d in xy:
            du = d.upper()
            cyc = cyclic[d]
            if hor_avg and (d in avg_dims) and (comp == "mean"):
                adv_i[du] = 0.
                continue
            if d in flux[du].dims:
                ds = d
                d = d + "_stag"
            else:
                ds = d + "_stag"
            dx = grid["D" + du]

            mf_flx = mapfac["F" + du]

            if dz_out:
                fac = dat_mean["RHOD_MEAN"]
            else:
                fac = dat_mean["MUT_MEAN"]
            if (comp == "mean") and hor_avg:
                mf_flx = avg_xy(mf_flx, avg_dims)
                fac = avg_xy(fac, avg_dims)
            if not dz_out:
                fac = build_mu(fac, grid, full_levels="bottom_top_stag" in flux[du].dims)
            fac = stagger_like(fac, flux[du], cyclic=cyclic)
            adv_i[du] = -diff(fac*flux[du]/mf_flx, ds, dat_mean[d], cyclic=cyc)*mf["X"]*mf["Y"]/dx
        fz = rhod8z_m*flux["Z"]
        if VAR == "W":
            adv_i["Z"] = -diff(fz, "bottom_top", grid["ZNW"])/grid["DN"]
            #set sfc and top point correctly
            adv_i["Z"][{"bottom_top_stag" : 0}] = 0.
            adv_i["Z"][{"bottom_top_stag" : -1}] = (2*fz.isel(bottom_top=-1)/grid["DN"][-2]).values

        else:
            adv_i["Z"] = -diff(fz, "bottom_top_stag", grid["ZNU"])/grid["DNW"]
        adv_i["Z"] = adv_i["Z"]*(-g)
        for d in adv_i.data_vars:
            if dz_out and (d != "Z"):
                adv_i[d] = adv_i[d]/grid["RHOD_STAG_MEAN"]
            else:
                adv_i[d] = adv_i[d]/grid["MU_STAG_MEAN"]

        adv[comp] = adv_i

    if hor_avg:
        adv["adv_r"] = avg_xy(adv["adv_r"], avg_dims)
        fluxes["adv_r"] = avg_xy(fluxes["adv_r"], avg_dims)

    keys = adv.keys()
    adv = xr.concat(adv.values(), "comp")
    adv = adv.to_array("dir")
    adv["comp"] = list(keys)
    flux = xr.concat(fluxes.values(), "comp")
    flux["comp"] = list(fluxes.keys())

    #resolved turbulent fluxes and tendencies
    flux = flux.reindex(comp=["adv_r", "mean", "trb_r"])
    adv = adv.reindex(comp=["adv_r", "mean", "trb_r"])
    for d in flux.data_vars:
        flux[d].loc["trb_r"] = flux[d].loc["adv_r"] - flux[d].loc["mean"]
        adv.loc[d, "trb_r"] = adv.loc[d, "adv_r"] - adv.loc[d, "mean"]

    return flux, adv, vmean, var_stag, corr

def cartesian_corrections(VAR, dim_stag, corr, var_stag, vmean, rhodm, grid, mapfac, adv, tend,
                          cyclic, dz_out=False, hor_avg=False, avg_dims=None):

    print("Compute Cartesian corrections")
    #decompose cartesian corrections
    #total
    corr = corr.expand_dims(comp=["adv_r"]).reindex(comp=["adv_r", "mean", "trb_r"])
    if hor_avg:
        corr = avg_xy(corr, avg_dims)
        rhodm = avg_xy(rhodm, avg_dims)

    #mean part
    for i, (d, v) in enumerate(zip(xy, ["U", "V"])):
        #staggering
        if hor_avg and (d in avg_dims):
            corr.loc["mean"][i] = 0
            continue
        kw = dict(ref=var_stag["Z"], cyclic=cyclic, **grid[stagger_const])
        rho_stag =  stagger_like(rhodm, **kw)
        if dz_out:
            corr_d = stagger_like(vmean[d.upper()], **kw)
        else:
            corr_d = stagger_like(grid["dzd{}_{}".format(d, v.lower())], **kw)

    corr.loc["mean"][i] = corr_d*rho_stag*var_stag["Z"]
    #resolved turbulent part
    corr.loc["trb_r"] = corr.loc["adv_r"] - corr.loc["mean"]

    #correction flux to tendency
    if "W" in VAR:
        dcorr_dz = diff(corr, "bottom_top", grid["ZNW"])/grid["DN"]
        dcorr_dz[{"bottom_top_stag" : 0}] = 0.
        dcorr_dz[{"bottom_top_stag" : -1}] = -(2*corr.isel(bottom_top=-1)/grid["DN"][-2]).values
    else:
        dcorr_dz = diff(corr, "bottom_top_stag", grid["ZNU"])/grid["DNW"]
    dcorr_dz = dcorr_dz/grid["MU_STAG_MEAN"]*(-g)
    #apply corrections
    for i, d in enumerate(XY):
        adv.loc[d] = adv.loc[d] + dcorr_dz[:, i]

    if dz_out:
        dcorr_dz = dcorr_dz*grid["dzdd"]
    tend = tend - dcorr_dz.sel(comp="adv_r", dir="T", drop=True)

    return adv, tend, corr

def total_tendency(dat_inst, var, grid, dz_out=False, hor_avg=False, avg_dims=None, **attrs):
    #instantaneous variable
    if var == "t":
        if attrs["USE_THETA_M"] and (not attrs["OUTPUT_DRY_THETA_FLUXES"]):
            if "THM" in dat_inst:
                vard = dat_inst["THM"]
            else:
                vard = (dat_inst["T"] + 300)*(1 + rvovrd*dat_inst["QVAPOR"]) - 300
        else:
            vard = dat_inst["T"]
    elif var == "q":
        vard = dat_inst["QVAPOR"]
    else:
        vard = dat_inst[var.upper()]

    #couple variable to mu
    if dz_out:
        rvar = vard*dat_inst["RHOD_STAG"]
    else:
        rvar = vard*dat_inst["MU_STAG"]

    # total tendency
    dt = int(dat_inst.Time[1] - dat_inst.Time[0])*1e-9
    total_tend = rvar.diff("Time")/dt

    if hor_avg:
        total_tend = avg_xy(total_tend, avg_dims)

    if dz_out:
        total_tend = total_tend/grid["RHOD_STAG_MEAN"]
    else:
        total_tend = total_tend/grid["MU_STAG_MEAN"]

    return total_tend
#%%prepare variables
def prepare(dat_mean, dat_inst, t_avg=False, t_avg_interval=None):
    print("Prepare data")
    attrs = dat_inst.attrs
    dat_inst.attrs = {}

    #strip first time as dat_inst needs to be one time stamp longer
    dat_mean = dat_mean.sel(Time=dat_mean.Time[1:])
    if len(dat_mean.Time) == 0:
        raise ValueError("dat_mean is empty! Needs to contain at least two timesteps initially!")
    if t_avg:
        avg_kwargs = dict(Time=t_avg_interval, coord_func={"Time" : partial(select_ind, indeces=-1)}, boundary="trim")
        dat_mean = dat_mean.coarsen(**avg_kwargs).mean()

    #computational grid
    grid = dat_inst[["ZNU","ZNW","DNW","DN","C1H","C2H","C1F","C2F",*stagger_const]].isel(Time=0, drop=True)
    grid["DN"] = grid["DN"].rename(bottom_top="bottom_top_stag").assign_coords(bottom_top_stag=grid["ZNW"][:-1]).reindex(bottom_top_stag=grid["ZNW"])
    grid["DX"] = attrs["DX"]
    grid["DY"] = attrs["DY"]

    dat_mean = dat_mean.assign_coords(bottom_top=grid["ZNU"], bottom_top_stag=grid["ZNW"])
    dat_inst = dat_inst.assign_coords(bottom_top=grid["ZNU"], bottom_top_stag=grid["ZNW"])

    dat_mean = dat_mean.rename(ZWIND_MEAN="W_MEAN")

    #select start and end points of averaging intervals
    dat_inst = dat_inst.sel(Time=[dat_inst.Time[0].values, *dat_mean.Time.values])
    for v in dat_inst.coords:
        if ("XLAT" in v) or ("XLONG" in v):
            dat_inst = dat_inst.drop(v)

    #check if periodic bc can be used in staggering operations
    cyclic = {d : bool(attrs["PERIODIC_{}".format(d.upper())]) for d in xy}
    cyclic["bottom_top"] = False

    return dat_mean, dat_inst, grid, cyclic, attrs

def calc_tend_sources(dat_mean, dat_inst, var, grid, cyclic, attrs, hor_avg=False, avg_dims=None):
    print("\nPrepare tendency calculations for {}".format(var.upper()))

    VAR = var.upper()
    dim_stag = None #for momentum: staggering dimension
    if var == "u":
        dim_stag = "x"
    elif var == "v":
        dim_stag = "y"
    elif var == "w":
        dim_stag = "bottom_top"

    #mapscale factors
    if var in ["u","v"]:
        mapfac_type = VAR
    else:
        mapfac_type = "M"
    mapfac_vnames = ["MAPFAC_{}X".format(mapfac_type),"MAPFAC_{}Y".format(mapfac_type)]
    mapfac = dat_inst[mapfac_vnames].isel(Time=0, drop=True)
    mapfac = mapfac.rename(dict(zip(mapfac_vnames,XY)))

    #map-scale factors for fluxes
    for d, m in zip(XY, ["UY", "VX"]):
        mf = dat_inst["MAPFAC_" + m].isel(Time=0, drop=True)
        flx = dat_mean["F{}{}_ADV_MEAN".format(var[0].upper(), d)]
        mapfac["F" + d] = stagger_like(mf, flx, cyclic=cyclic)

    dat_mean["FUY_SGS_MEAN"] = dat_mean["FVX_SGS_MEAN"]

    #density and dry air mass
    mu = grid["C2H"]+ grid["C1H"]*(dat_inst["MU"]+ dat_inst["MUB"])
    dat_inst["MU_STAG"] = mu
    grid["MU_STAG_MEAN"] = grid["C2H"]+ grid["C1H"]*dat_mean["MUT_MEAN"]
    rhodm = dat_mean["RHOD_MEAN"]
    if var in uvw:
        rhodm = stagger(rhodm, dim_stag, dat_inst[dim_stag + "_stag"], cyclic=cyclic[dim_stag], **grid[stagger_const])
        if var == "w":
            dat_inst["MU_STAG"] = grid["C2F"] + grid["C1F"]*(dat_inst["MU"]+ dat_inst["MUB"])
            grid["MU_STAG_MEAN"] = grid["C2F"] + grid["C1F"]*dat_mean["MUT_MEAN"]
        else:
            dat_inst["MU_STAG"] = stagger(dat_inst["MU_STAG"], dim_stag, dat_inst[dim_stag + "_stag"], cyclic=cyclic[dim_stag])
            grid["MU_STAG_MEAN"] = stagger(grid["MU_STAG_MEAN"], dim_stag, dat_mean[dim_stag + "_stag"], cyclic=cyclic[dim_stag])

    ref = rhodm
    if hor_avg:
        rhodm = avg_xy(rhodm, avg_dims)
    grid["RHOD_STAG_MEAN"] = rhodm

    #derivative of z wrt x,y,t
    dzdd = xr.Dataset()
    for d in xy:
        du = d.upper()
        dzdd[du] = diff(dat_mean["Z_MEAN"], d, dat_mean[d + "_stag"], cyclic=cyclic[d])/grid["D" + du]

    zw_inst = (dat_inst["PH"] + dat_inst["PHB"])/g
    dt = int(dat_inst.Time[1] - dat_inst.Time[0])*1e-9
    dzdd["T"] = zw_inst.diff("Time")/dt
    for d in [*XY, "T"]:
        dzdd[d] = stagger_like(dzdd[d], ref, ignore=["bottom_top_stag"], cyclic=cyclic)
    dzdd = remove_deprecated_dims(dzdd)
    grid["dzdd"] = dzdd.to_array("dir")

    for d, vel in zip(XY, ["u", "v"]):
        dph = -dat_mean["DPH_{}_MEAN".format(d)]/g
        grid["dzd{}_{}".format(d.lower(), vel)] = stagger_like(dph, ref, ignore=["bottom_top_stag"], cyclic=cyclic)

    rhod = - 1/diff(g*zw_inst, "bottom_top_stag", dat_inst.bottom_top)*grid["DNW"]*mu
    dat_inst["RHOD_STAG"] = stagger_like(rhod, ref, cyclic=cyclic)

    #height
    grid["ZW"] = dat_mean["Z_MEAN"]
    grid["Z_STAG"] = stagger_like(dat_mean["Z_MEAN"], ref, cyclic=cyclic)

    #additional sources
    print("Compute SGS and additional tendencies")

    sources = xr.Dataset()
    if var == "t":
        sources["mp"] = dat_mean["T_TEND_MP_MEAN"]
        sources["rad_lw"] = dat_mean["T_TEND_RADLW_MEAN"]
        sources["rad_sw"] = dat_mean["T_TEND_RADSW_MEAN"]
        if attrs["USE_THETA_M"] and (not attrs["OUTPUT_DRY_THETA_FLUXES"]):
            #convert sources from dry to moist theta
            sources = sources*(1 + rvovrd*dat_mean["Q_MEAN"])
            #add mp tendency
            sources["mp"] = sources["mp"] + dat_mean["Q_TEND_MP_MEAN"]*rvovrd*(dat_mean["T_MEAN"] + 300)
    elif var == "q":
        sources["mp"] = dat_mean["Q_TEND_MP_MEAN"]
    else:
        sources["pg"] = dat_mean["{}_TEND_PG_MEAN".format(VAR)]
        sources["cor_curv"] = dat_mean["{}_TEND_COR_CURV_MEAN".format(VAR)]

    #calculate tendencies from sgs fluxes and corrections
    sgs, sgsflux = sgs_tendency(dat_mean, VAR, grid, dzdd, cyclic, dim_stag=dim_stag, mapfac=mapfac)

    if hor_avg:
        sources = avg_xy(sources, avg_dims)
        sgs = avg_xy(sgs, avg_dims)
        sgsflux = avg_xy(sgsflux, avg_dims)
        grid = avg_xy(grid, avg_dims)

    sources = sources.to_array("comp")
    sources_sum = sources.sum("comp") + sgs.sum("dir", skipna=False)

    return dat_mean, dat_inst, sgs, sgsflux, sources, sources_sum, grid, dim_stag, mapfac


def build_mu(mut, grid, full_levels=False):
    if full_levels:
        mu = grid["C1F"]*mut + grid["C2F"]
    else:
        mu = grid["C1H"]*mut + grid["C2H"]
    return mu
#%% plotting
def scatter_tend_forcing(tend, forcing, var, plot_diff=False, hue="bottom_top", savefig=True, title=None, fname=None, figloc=figloc, **kwargs):
    if title is None:
        title = fname
    fig, ax, cax = scatter_hue(tend, forcing, plot_diff=plot_diff, hue=hue, title=title,  **kwargs)
    if var in tex_names:
        tex_name = tex_names[var]
    else:
        tex_name = var
    xlabel = "Total ${}$ tendency".format(tex_name)
    ylabel = "Total ${}$ forcing".format(tex_name)
    if plot_diff:
        ylabel += " - " + xlabel
    units = " ({})".format(units_dict_tend[var])
    ax.set_xlabel(xlabel + units)
    ax.set_ylabel(ylabel + units)

    if savefig:
        fig.savefig(figloc + "{}_budget/scatter/{}.png".format(var, fname),dpi=300, bbox_inches="tight")

    return fig

def scatter_hue(dat1, dat2, plot_diff=False, hue="bottom_top", discrete=False, iloc=None, loc=None, title=None, **kwargs):
    if iloc is not None:
        for d, val in iloc.items():
            if (d not in dat1.coords) and (d + "_stag" in dat1.coords):
                iloc[d + "_stag"] = val
                del iloc[d]
        dat1 = dat1[iloc]
        dat2 = dat2[iloc]
    if loc is not None:
        for d, val in loc.items():
            if (d not in dat1.coords) and (d + "_stag" in dat1.coords):
                loc[d + "_stag"] = val
                del loc[d]
        dat1 = dat1.loc[loc]
        dat2 = dat2.loc[loc]
    pdat = xr.concat([dat1, dat2], "concat_dim")
    err = abs(dat1 - dat2)
    rmse = (err**2).mean().values**0.5
    r2 = np.corrcoef(pdat[0].values.flatten(), pdat[1].values.flatten())[1,0]

    if plot_diff:
        pdat[1] = pdat[1] - pdat[0]

    if (hue not in pdat.coords) and (hue + "_stag" in pdat.coords):
        hue = hue + "_stag"

    n_hue = len(pdat[hue])
    hue_int = np.arange(n_hue)
    pdat = pdat.assign_coords(hue=(hue, hue_int))
    pdatf = pdat[0].stack(s=pdat[0].dims)

    #set color
    cmap = "cool"
    if ("bottom_top" in hue) and (not discrete):
        color = -pdatf[hue]
    elif (hue == "Time") and (not discrete):
        color = pdatf["hue"]
    else:
        color = pdatf[hue]
        try:
            color.astype(int) #check if hue is numeric
        except:
            discrete = True
        if discrete:
            cmap = plt.get_cmap("tab10", n_hue)
            if n_hue > 10:
                raise ValueError("Too many different hue values for cmap tab10!")
            discrete = True
            color = pdatf["hue"]


    kwargs.setdefault("cmap", cmap)

    fig, ax = plt.subplots()
    kwargs.setdefault("s", 10)
    p = plt.scatter(pdat[0], pdat[1], c=color.values, **kwargs)
    labels = []
    for dat in [dat1, dat2]:
        label = ""
        if dat.name is not None:
            label = dat.name
        elif "description" in dat.attrs:
            label = dat.description
        if label != "":
            if "units" in dat.attrs:
                label += " ({})".format(dat.units)
        labels.append(label)
    plt.xlabel(labels[0])
    plt.ylabel(labels[1])

    for i in [0,1]:
        pdat = pdat.where(~pdat[i].isnull())
    if not plot_diff:
        minmax = [pdat.min(), pdat.max()]
        dist = minmax[1] - minmax[0]
        minmax[0] -= 0.03*dist
        minmax[1] += 0.03*dist
        plt.plot(minmax, minmax, c="k")
        ax.set_xlim(minmax)
        ax.set_ylim(minmax)

    #colorbar
    cax = fig.add_axes([0.84,0.1,0.1,0.8], frameon=False)
    cax.set_yticks([])
    cax.set_xticks([])
    clabel = hue
    if "bottom_top" in hue:
        clabel = "$\eta$"
    if ("bottom_top" in hue) and (not discrete):
        cb = plt.colorbar(p,ax=cax,label=clabel)
        cb.set_ticks(np.arange(-0.8,-0.2,0.2))
        cb.set_ticklabels(np.linspace(0.8,0.2,4).round(1))
    else:
        cb = plt.colorbar(p,ax=cax,label=clabel)
        if discrete:
            if n_hue > 1:
                d = (n_hue-1)/n_hue
                cb.set_ticks(np.arange(d/2, n_hue-1, d))
            else:
                cb.set_ticks([0])

            cb.set_ticklabels(pdat[hue].values)

    #error labels
    ax.text(0.74,0.07,"RMSE={0:.2E}\nR$^2$={1:.5f}".format(rmse, r2), horizontalalignment='left',
             verticalalignment='bottom', transform=ax.transAxes)
    if title is not None:
        fig.suptitle(title)

    return fig, ax, cax