#! /usr/bin/env python
"""Module for comparing NetCDF files against a NetCDF file template"""

import netCDF4
import os
import sys
import argparse
import traceback
import numpy as np
from typing import Union
import re
import configparser

from numpy.ma.core import masked_invalid, minimum_fill_value
from pandas.core.ops.invalid import make_invalid_op

default_nc_template = os.path.join(os.path.dirname(__file__), 'templates/IOOS_Glider_NetCDF_v2.0.nc')

def main(args):
    """Validate each specified NetCDF file against a NetCDF template and print
    the results STDOUT.  Errors are printed to STDERR."""

    # Read config file with specifications for valid range of variable values
    config = load_config(args.config)
    
    if not args.nc_files:
        sys.stderr.write('No NetCDF files specified for validation\n')
        return 1

    for nc_file in args.nc_files:
        validated = validate_ioosdac_nc_file(nc_file, config, nc_template=args.template)
        if validated:
            sys.stdout.write('Valid file: {:s}\n'.format(nc_file))
        else:
            sys.stdout.write('INVALID file: {:s}\n'.format(nc_file))
        sys.stdout.write('{:s}\n'.format('=' * 86))

    
    return 0
            
def validate_ioosdac_nc_file(nc_file, config, nc_template=default_nc_template):
    """Validate the NetCDF file against the nc_template NetCDF file.
    
    The specified nc_file is compared against the default_nc_template, which
    should be a NetCDF file fully conforming to the IOOS National Glider Data
    Assembly Center specification.
    """
    
    validated = True
    
    # Make sure the file exists
    if not nc_file:
        sys.stderr.write('No NetCDF file specified for validation.\n')
        sys.stderr.flush()
        return False
    elif not os.path.exists(nc_file):
        sys.stderr.write('Invalid NetCDF file specified: {:s}\n'.format(nc_file))
        sys.stderr.flush()
        return False
    
    sys.stdout.write('Validating file   : {:s}\n'.format(nc_file))
    sys.stdout.write('Validating against: {:s}\n'.format(nc_template))
    sys.stdout.flush()
    
    (nc_path, nc_name) = os.path.split(nc_file)

    # Open up the template and file to validate

    nct = netCDF4.Dataset(nc_template)

    try:    
        nc = netCDF4.Dataset(nc_file)
    except Exception:
        traceback.print_exc()
        validated = False
        print(f">>> File could not be read. Will go to next file (if any)")
        return validated
    
    # 1. Check global attribures
    global_att_count = 0
    nc_global_atts = nc.ncattrs()
    for att in nct.ncattrs():
        if att not in nc_global_atts:
            sys.stderr.write(' GlobalAttributeError: Missing global attribute: {:s}\n'.format(
                att))
            sys.stderr.flush()
            validated = False
            continue
            
        global_att_count += 1
            
    # 1. Check dimensions
    nc_dim_count = 0
    nc_dim_names = nc.dimensions.keys()
    for dim in nct.dimensions.keys():
        if dim not in nc_dim_names:
            sys.stderr.write(' DimensionEror: Missing dimension: {:s}\n'.format(
                dim))
            sys.stderr.flush()
            validated = False
            continue
            
        nc_dim_count += 1
        
    # 2. Check variables
    nc_var_count = 0
    nc_var_names = nc.variables.keys()
    for var in nct.variables.keys():
        if var not in nc_var_names:
            sys.stderr.write(' VariableError: Missing variable: {:s}\n'.format(
                var))
            sys.stderr.flush()
            validated = False
            continue
        
        # Store reference to current variable
        nc_var = nc.variables[var]
        # Store reference to template variable
        nct_var = nct.variables[var]
        
        # Check datatype
        if nc_var.dtype != nct_var.dtype:
            sys.stderr.write('  VariableError: Incorrect datatype for {:s} ({:s}!={:s})\n'.format(
                var,
                str(nc_var.dtype.type),
                str(nct_var.dtype.type)))
            sys.stderr.flush()
            validated = False
        
        # Check variable dimension
        if nct.variables[var].dimensions != nc.variables[var].dimensions:
            sys.stderr.write('  VariableError: Incorrect dimension for {:s} ({:s}!={:s}\n'.format(
                var,
                str(nct.variables[var].dimensions),
                str(nc.variables[var].dimensions)))
            validated = False
        
        # Check variable attributes
        nc_var_atts = nc.variables[var].ncattrs()
        for var_att in nct.variables[var].ncattrs():
            if var_att not in nc_var_atts:
                sys.stderr.write('   VariableError: Missing attribute for {:s}: {:s}\n'.format(
                    var,
                    var_att))
                sys.stderr.flush()
                validated = False

        # Check variable contents
        mini, maxi = read_bounds(config, var)
        var_cont_valid = check_variable_contents(var, nc_var, mini, maxi)
        validated = validated and var_cont_valid

        nc_var_count = nc_var_count + 1
    
    sys.stdout.write('\n{:s} RESULTS {:s}\n'.format('=' * 39, '=' * 39))
    sys.stdout.write('{:d}/{:d} required global attributes validated\n'.format(
        global_att_count,
        len(nct.ncattrs())))
    sys.stdout.write('{:d}/{:d} required dimensions validated\n'.format(
        nc_dim_count,
        len(nct.dimensions)))
    sys.stdout.write('{:d}/{:d} required variables validated\n'.format(
        nc_var_count,
        len(nct.variables)))
    sys.stdout.write('{:s}\n'.format('=' * 86))
    sys.stdout.flush()
    
    return validated


def check_variable_contents(varname: str, nc_var:netCDF4._netCDF4.Variable, mini: Union[int,float]=None, maxi: Union[int,float]=None):

    """
    Check the contents of a netCDF variable for validity based on specified criteria.

    Parameters:
    ----------
    nc_var : netCDF4._netCDF4.Variable
        The netCDF variable object to check. This variable should be compatible
        with NumPy-style indexing and have attributes such as `long_name` and
        optionally `missing_value`, `_FillValue`, or `fill_value`.
    mini : Union[int, float], optional
        The minimum valid value for the variable. If provided, all values in the
        variable array must be greater than or equal to this value for the
        variable to be considered valid.
    maxi : Union[int, float], optional
        The maximum valid value for the variable. If provided, all values in the
        variable array must be less than or equal to this value for the variable
        to be considered valid.

    Returns:
    -------
    valid : bool
        True if the variable is considered valid based on the following criteria:
        - The variable array contains more than one unique value, or if it has only
          one value, that value does not match the defined missing/fill value.
        - All values in the variable array are within the range defined by `mini`
          and `maxi` (if these bounds are provided).
        False otherwise, indicating the variable is invalid based on one or more of
        the criteria.
    """

    print(f">>> Checking contents of variable {varname}...")

    valid = True

    v_arr = nc_var[...]

    # Check if contents of a variable are all equal
    unique = np.unique(v_arr)
    dv = len(unique)
    if dv == 1:
        print(f">>> WARNING! Elements in variable array {varname} equal only one value: {unique[0]}")

        # Check if that corresponds to missing value
        for fv in ["missing_value", "_FillValue", "fill_value"]:

            try:
                fill = getattr(nc_var, fv)
                print(f"{fv}={fill}")
                if fill == unique[0]:
                    print(f"...All elements in {varname} correspond to fill value! Variable invalid!")
                    valid = False
                    return valid
                break
            except AttributeError:
                pass

    # If minimum valid value is provided, all values in the variable array must be greater than or equal to this value
    if mini is not None:
        if len(np.where(v_arr < mini)[0]) == 0:
            print(f">>> All elements in variable array {varname} are less than minimum: {mini}. Variable invalid!")
            valid = False
            return valid

    # If maximum valid value is provided, all values in the variable array must be smaller than or equal to this value
    if maxi is not None:
        if len(np.where(v_arr > maxi)[0]) == 0:
            print(f">>> All elements in variable array {varname} are larger than maximum: {maxi}. Variable invalid!")
            valid = False
            return valid

    return valid


def load_config(path:str):
    config = configparser.ConfigParser()
    config.read(path)
    return config

def read_bounds(config, vari:str) -> tuple[float, float]:
    '''
    Read in the maximum and minimum valid values of a variable from the config file;
    use regex pattern matching (curly braces in the config file are replaced with square ones).
    If the variable can't be found in the config file, use the category "general".
    '''

    # Loop through sections in config file
    for pattern in config.sections():
        # replace braces in order to get regex pattern
        pattern = pattern.replace('(', '[').replace(')', ']')
        # Find the section in config file matching the variable name
        if re.fullmatch(pattern, vari):
            minv = float(config[pattern]["min"])
            maxv = float(config[pattern]["max"])
            return minv, maxv

    # if no matching section is found, use section "general"
    minv = float(config["general"]["min"])
    maxv = float(config["general"]["max"])
    return minv, maxv

    
if __name__ == '__main__':
    
    arg_parser = argparse.ArgumentParser(description=main.__doc__)
    arg_parser.add_argument('nc_files',
        nargs='*',
        default=[],
        help='One or more NetCDF files to parse')
    arg_parser.add_argument('-t', '--template',
        default=default_nc_template,
        help='Alternate template to validate against (Default={:s}'.format(default_nc_template))
    arg_parser.add_argument('-c', '--config', default="./settings.cfg", help="Path to config file")
    args = arg_parser.parse_args()

    main(args)
    
    
