Quick & Dirty NetCDF File Validation
====================================

A python module for comparing one or more NetCDF files against a known NetCDF
template and checking data integrity. Results are printed to STDOUT and errors 
(i.e.: missing dimensions, variables, global and variable attributes) are printed 
to STDERR.

The comparison is very simple.  The template file is read and then compared to
the structure of each of the files specified on the command line. 
In addition, data integrity is checked; i.e., whether variables contain only 
fill values or values outside the valid range. 

The following items are checked:

1. Inclusion of proper dimension variables
2. Inclusion of global attributes
3. Inclusion of proper variables
4. Datatypes of included variables
5. Attributes of included variables
6. Data integrity

###Required Non-Core Python modules:###

The following modules are required and not typically installed with standard python distributions and can be installed using pip:

    >> pip install netcdf4

The [Anaconda](https://store.continuum.io/cshop/anaconda/) and [Enthought Python Distribution](https://www.enthought.com/products/epd/) python distributions come with these modules installed.

- [netCDF4](https://github.com/Unidata/netcdf4-python)
- [numpy](http://www.numpy.org/) (Installed as dependency for netCDF4)

###Usage###

    > nc_validate -h

for usage.

The module may be executed from the command line.  If run this way, the
specified files are compared to the template file contained in:

    ./templates/IOOS_Glider_NetCDF_v2.0.nc

If you would like to change the file against which the specified files are
compared, you can do one of the following:

- Use the -t or --template option and specify the location of the template
file.

Run the script like this:

    > nc_validate.py --template PATH_TO_TEMPLATE FILE1[, FILE2, ...]

- Put the file somewhere and specify its location in the <b>default_nc_template</b> variable (line #9).

Then run the script like this:

    > nc_validate.py FILE1[, FILE2, ...]

The valid range for each variable of your netCDF files can be set in a config file, 
e.g., settings.cfg. 
Each variable goes into a section of the config file in square brackets like this:

```
[temperature]
min = -50
max = 50
```

You may summarize different variable names using regular expressions (regex), 
but use round brackets instead of square ones, since the latter are interpreted 
as sections in the cfg file structure.

The path to the config file is `./settings.cfg` by default, but may be specified 
using the `-c` command line argument:

    > nc_validate.py FILE1[, FILE2, ...] -c /path/to/config.cfg