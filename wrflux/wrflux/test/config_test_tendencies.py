#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 22 17:36:46 2019

Settings for launch_jobs.py
Test settings for automated tests.

@author: Matthias Göbel

"""
import os
import numpy as np
from run_wrf.configs.base_config import *
from copy import deepcopy
params = deepcopy(params)

# %%
'''Simulations settings'''

runID = "pytest"  # name for this simulation series

params["outpath"] = os.environ["wrf_res"] + "/test/" + runID  # WRF output path root
params["run_path"] = os.environ["wrf_runs"] + "/test/" + runID  # path where run directories of simulations will be created
params["build_path"] = os.environ["wrf_builds"]  # path where different versions of the compiled WRF model code reside
serial_build = "WRF_fluxmod"  # used if nslots=1
parallel_build = "WRF_fluxmod"  # used if nslots > 1
debug_build = "WRF_fluxmod_debug"  # used for -d option

o = np.arange(2, 7)
# names of parameter values for output filenames
# either dictionaries or lists (not for composite parameters)
param_names = {"th": ["thd", "thm", "thdm"],
               "h_adv_order": [2, 3],
               "v_adv_order": [2, 3],
               "adv_order": o,
               "bc": ["open"],
               "timing": ["short"]}

# Fill dictionary params with default values to be used for parameters not present in param_grid

params["start_time"] = "2018-06-20_12:00:00"  # format %Y-%m-%d_%H:%M:%S
params["end_time"] = "2018-06-20_13:00:00"  # format %Y-%m-%d_%H:%M:%S

params["n_rep"] = 1  # number of repetitions for each configuration

# horizontal grid
params["dx"] = 500  # horizontal grid spacing x-direction(m)
params["dy"] = None  # horizontal grid spacing y-direction (m), if None: dy = dx
params["lx"] = 10000  # minimum horizontal extent in east west (m)
params["ly"] = 10000  # minimum horizontal extent in north south (m)

# control vertical grid creation (see vertical_grid.py for details on the different methods)
params["ztop"] = 3000  # top of domain (m)
params["zdamp"] = int(params["ztop"] / 5)  # depth of damping layer (m)
params["damp_opt"] = 0
params["nz"] = None  # number of vertical levels
params["dz0"] = 60  # height of first model level (m)
# if nz is None and for vgrid_method=0 only: specify maximum vertical grid spacing instead of nz;
# either float or "dx" to make it equal to dx
params["dzmax"] = 300
# method for creating vertical grid as defined in vertical_grid.py
# if None: do not change eta_levels
params["vgrid_method"] = 1

params["dt_f"] = 2  # time step (s), if None calculated as dt = 6 s/m *dx/1000; can be float
params["spec_hfx"] = None

params["input_sounding"] = "unstable"  # name of input sounding to use (final name is then created: input_sounding_$name)
params["hm"] = 500  # mountain height (m)

# other standard namelist parameters
params["mp_physics"] = 0
params["bl_pbl_physics"] = 0
params["ra_lw_physics"] = 1
params["ra_sw_physics"] = 1
params["sf_surface_physics"] = 2

params["km_opt"] = 2
params["khdif"] = 0.
params["kvdif"] = 0.
params["use_theta_m"] = 1
params["mix_isotropic"] = 0
params["momentum_adv_opt"] = 1
params["moist_adv_opt"] = 1
params["scalar_adv_opt"] = 1
params["h_sca_adv_order"] = 5
params["v_sca_adv_order"] = 3
params["h_mom_adv_order"] = 5
params["v_mom_adv_order"] = 3

# indices for output streams and their respective name and output interval (minutes, floats allowed)
# 0 is the standard output stream
params["output_streams"] = {24: ["meanout", 30.], 0: ["instout", 30.]}

params["output_t_fluxes"] = 1
params["output_q_fluxes"] = 1
params["output_u_fluxes"] = 1
params["output_v_fluxes"] = 1
params["output_w_fluxes"] = 1
params["output_t_fluxes_small"] = 1
params["output_t_fluxes_add"] = 1
params["output_q_fluxes_add"] = 1
params["output_u_fluxes_add"] = 1
params["output_v_fluxes_add"] = 1
params["output_w_fluxes_add"] = 1
params["hesselberg_avg"] = True
params["output_dry_theta_fluxes"] = True

params["restart_interval_m"] = 30  # restart interval (min)
params["iofields_filename"] = "IO_file.txt"

# registries to look for default namelist parameters
registries.append("registry.avgflx")

params["min_nx_per_proc"] = 10  # 25, minimum number of grid points per processor
params["min_ny_per_proc"] = 10  # 25, minimum number of grid points per processor
