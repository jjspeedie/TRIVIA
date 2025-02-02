import numpy as np
import pandas as pd
import cmasher as cmr
import plotly.express as px
import plotly.graph_objects as go
from scipy.interpolate import RegularGridInterpolator
from scipy.interpolate import CubicSpline
from gofish import imagecube
from matplotlib import cm
from matplotlib.colors import ListedColormap, LinearSegmentedColormap

def concatenate_cmaps(cmap1, cmap2, ratio=None, ntot=None):
    """
    Concatenate two colormaps.
    https://matplotlib.org/stable/tutorials/colors/colormap-manipulation.html

    Args:
        cmap1 (str): Name of the first colormap (bottom) to concatenate.
        cmap2 (str): Name of the second colormap (top) to concatenate.
        ratio (Optional[float]): The ratio between the first and second colormap.
        ntot (Optional[int]): The number of levels in the concatenated colormap.
    """
    ratio = 0.5 if ratio is None else ratio
    ntot = 256 if ntot is None else ntot

    bottom = cm.get_cmap(cmap1, ntot)
    top = cm.get_cmap(cmap2, ntot)
    nbottom = int(ratio*ntot)
    ntop = ntot-nbottom
    newcolors = np.vstack((bottom(np.linspace(0, 1, nbottom)),
                       top(np.linspace(0, 1, ntop))))
    newcmp = ListedColormap(newcolors, name='newcolormap')
    newcmp = np.around(newcmp(range(ntot)),decimals=4)
    colorscale = [[f, 'rgb({}, {}, {})'.format(*newcmp[ff])]
              for ff, f in enumerate(np.around(np.linspace(0, 1, newcmp.shape[0]),decimals=4))]
    return colorscale

def make_colorscale(cmap):
    """
    Convert a color table into a CSS-compatible color table.

    Args:
        cmap (str): Color table name. e.g., 'cmr.pride'

    Returns:
        A list containing CSS-compatible color table.
    """
    cmarr = np.array(cmr.take_cmap_colors(cmap, 128))
    colorscale = [[f, 'rgb({}, {}, {})'.format(*cmarr[ff])]
                  for ff, f in enumerate(np.linspace(0, 1, cmarr.shape[0]))]
    return colorscale

def make_cm(path, clip=3., fmin=None, fmed=None, fmax=None, vmin=None, vmax=None,
            xmin=None, xmax=None, ymin=None, ymax=None,
            nx=None, ny=None, cmap=None, nointerp=False, show_figure=False, write_html=True):
    """
    Make interactive channel map.

    Args:
        path (str): Relative path to the FITS cube.
        clip (Optional[float]): Plot cube.data < clip * cube.rms in black and white.
        fmin (Optional[float]): The lower bound of the flux.
        fmed (Optional[float]): The boundary between bw/color cmaps.
        fmax (Optional[float]): The upper bound of the flux.
        vmin (Optional[float]): The lower bound of the velocity in km/s.
        vmax (Optional[float]): The upper bound of the velocity in km/s.
        xmin (Optional[float]): The lower bound of X range.
        xmax (Optional[float]): The upper bound of X range.
        ymin (Optional[float]): The lower bound of Y range.
        ymax (Optional[float]): The upper bound of Y range.
        nx (Optional[float]): Number of x pixels.
        ny (Optional[float]): Number of y pixels.
        cmap (Optional[str]): Color map to use.
        nointerp (Optional[bool]): If True, no interpolation applied to the data.
        show_figure (Optional[bool]): If True, show channel map.
        write_html (Optional[bool]): If True, write channel map in a html file.
    Returns:
        Interactive channel map in a html format.
    """
    # Read in the FITS data.
    cube = imagecube(path)
    cube.data = cube.data.astype(float)

    fmin = 0. if fmin is None else fmin
    fmed = clip*cube.rms if fmed is None else fmed
    fmax = cube.data.max()*0.7 if fmax is None else fmax
    funit = 'Jy/beam'
    if fmax < 0.5 :
        cube.data *= 1.0e3
        fmin *= 1.0e3
        fmed *= 1.0e3
        fmax *= 1.0e3
        funit = 'mJy/beam'

    if xmin is None:
        xmin = cube.FOV/2.0
        i = -1
    else:
        xmin = xmin
        i = np.abs(cube.xaxis - xmin).argmin()
        i += 1 if cube.xaxis[i] < xmin else 0
    if xmax is None:
        xmax = -cube.FOV/2.0
        j = -1
    else:
        xmax = xmax
        j = np.abs(cube.xaxis - xmax).argmin()
        j -= 1 if cube.xaxis[j] > xmax else 0

    cube.xaxis = cube.xaxis[j+1:i]
    cube.data = cube.data[:,:,j+1:i]

    if ymin is None:
        ymin = -cube.FOV/2.0
        i = 0
    else:
        ymin = ymin
        i = np.abs(cube.yaxis - ymin).argmin()
        i += 1 if cube.yaxis[i] < ymin else 0
    if ymax is None:
        ymax = cube.FOV/2.0
        j = -1
    else:
        ymax = ymax
        j = np.abs(cube.yaxis - ymax).argmin()
        j -= 1 if cube.yaxis[j] > ymax else 0

    cube.yaxis = cube.yaxis[i:j]
    cube.data = cube.data[:,i:j,:]

    # Crop the data along the velocity axis, implemented from gofish
    vmin = cube.velax[0] if vmin is None else vmin*1.0e3
    vmax = cube.velax[-1] if vmax is None else vmax*1.0e3
    i = np.abs(cube.velax - vmin).argmin()
    i += 1 if cube.velax[i] < vmin else 0
    j = np.abs(cube.velax - vmax).argmin()
    j -= 1 if cube.velax[j] > vmax else 0
    cube.velax = cube.velax[i:j+1]
    cube.data = cube.data[i:j+1]

    if (cube.velax.shape[0] > 200.):
        print("Warning: There are total", cube.velax.shape[0], "channels. The output file can be very large! Consider using a smaller velocity range by changing vmin and vmax.")

    # Interpolate the cube on the RA-Dec plane
    # Caution: This is only for visualization purposes.
    # Avoid using this interpolation routine for scientific purposes.
    if not nointerp:
        nx = 400 if nx is None else nx
        ny = 400 if ny is None else ny

        oldx = cube.xaxis
        oldy = cube.yaxis

        cube.xaxis = np.linspace(cube.xaxis[0],cube.xaxis[-1],nx)
        cube.yaxis = np.linspace(cube.yaxis[0],cube.yaxis[-1],ny)
        cube.nxpix, cube.nypix = nx, ny

        newx, newy = np.meshgrid(cube.xaxis, cube.yaxis)
        newdata = np.zeros((cube.data.shape[0],ny,nx))

        for i in np.arange(cube.data.shape[0]):
            interp_func = RegularGridInterpolator((oldy, oldx[::-1]), cube.data[i])
            newdata[i] = interp_func(np.array([newy.flatten(), newx.flatten()]).T).reshape((ny,nx))[:,::-1]
        cube.data = newdata
    else:
        print("Warning: No interpolation will perform. The output file can be very large!")

    cube.xaxis = np.around(cube.xaxis,decimals=3)
    cube.yaxis = np.around(cube.yaxis,decimals=3)

    toplot = np.around(cube.data,decimals=3)

    cmap = concatenate_cmaps('binary','inferno',ratio=fmed/fmax) if cmap is None else concatenate_cmaps('binary',cmap,ratio=fmed/fmax)

    fig = px.imshow(toplot, color_continuous_scale=cmap, origin='lower',
                    x=cube.xaxis, y=cube.yaxis,
                    zmin=fmin, zmax=fmax,
                    labels=dict(x="RA offset [arcsec]", y="Dec offset [arcsec]",
                                color="Intensity ["+funit+"]", animation_frame="channel"),
                    animation_frame=0,
                   )
#    fig.update_xaxes(range=[xmin, xmax],autorange=False)
#    fig.update_yaxes(range=[ymax, ymin],autorange=False)
    fig.update_xaxes(autorange="reversed")
    fig.update_xaxes(ticks="outside")
    fig.update_yaxes(ticks="outside")
    for i, frame in enumerate(fig.frames):
        frame['layout'].update(title_text="v = {:.2f} km/s".format(cube.velax[i]/1.0e3),
                               title_x=0.5,
                              )

    if show_figure:
       fig.show()
    if write_html:
       fig.write_html(path.replace('.fits', '_channel.html'), include_plotlyjs='cdn')
    return

# def plot_keplerian_surface(cube, inc, PA, mstar, dist, x0=0.0, y0=0.0, vlsr=0.0,
#               z0=None, psi=None, r_cavity=None, r_taper=None, q_taper=None,
#               z1=None, phi=None, z_func=None, r_min=None, r_max=None,
#               cylindrical=False, shadowed=False):
#     """
#     Plot projected Keplerian velocity profile as a surface onto PPV diagram.
#
#         Args:
#             <<<<< From Rich Teague's gofish >>>>>
#             inc (float): Inclination of the disk in [degrees].
#             PA (float): Position angle of the disk in [degrees],
#                 measured east-of-north towards the redshifted major axis.
#             mstar (float): Stellar mass in [Msun].
#             dist (float): Distance to the source in [pc].
#             x0 (Optional[float]): Source center offset along the x-axis in
#                 [arcsec].
#             y0 (Optional[float]): Source center offset along the y-axis in
#                 [arcsec].
#             vlsr (Optional[float]): Systemic velocity in [m/s].
#             z0 (Optional[float]): Emission height in [arcsec] at a radius of
#                 1".
#             psi (Optional[float]): Flaring angle of the emission surface.
#             r_cavity (Optional[float]): Edge of the inner cavity for the
#                 emission surface in [arcsec].
#             r_taper (Optional[float]): Characteristic radius in [arcsec] of the
#                 exponential taper to the emission surface.
#             q_taper (Optional[float]): Exponent of the exponential taper of the
#                 emission surface.
#             z1 (Optional[float]): Correction to emission height at 1" in
#                 [arcsec].
#             phi (Optional[float]): Flaring angle correction term.
#             z_func (Optional[callable]): A function which returns the emission
#                 height in [arcsec] for a radius given in [arcsec].
#             r_min (Optional[float]): The inner radius in [arcsec] to model.
#             r_max (Optional[float]): The outer radius in [arcsec] to model.
#             cylindrical (Optional[bool]): If ``True``, force cylindrical
#                 rotation, i.e. ignore the height in calculating the velocity.
#             shadowed (Optional[bool]): If ``True``, use a slower algorithm for
#                 deprojecting the pixel coordinates into disk-center coordiantes
#                 which can handle shadowed pixels.
#     """
#     # Projected Keplerian velocity profile in [km/s] from gofish
#     v_los  = cube.keplerian(
#                   inc=inc,
#                   PA=PA,
#                   mstar=mstar,
#                   dist=dist,
#                   x0=x0,
#                   y0=y0,
#                   vlsr=vlsr,
#                   z0=z0,
#                   psi=psi,
#                   r_cavity=r_cavity,
#                   r_taper=r_taper,
#                   q_taper=q_taper,
#                   z1=z1,
#                   phi=phi,
#                   z_func=z_func,
#                   r_min=r_min,
#                   r_max=r_max,
#                   cylindrical=cylindrical,
#                   shadowed=shadowed)      * 1e3


def make_ppv(path, path_to_mask=None, clip=3., rms=None, rmin=None, rmax=None, N=None,
        cmin=None, cmax=None, constant_opacity=None, ntrace=20,
        marker_size=2, cmap=None, hoverinfo='x+y+z', colorscale=None, xaxis_title=None,
        yaxis_title=None, zaxis_title=None, xaxis_backgroundcolor=None, xaxis_gridcolor=None,
        yaxis_backgroundcolor=None, yaxis_gridcolor=None,
        zaxis_backgroundcolor=None, zaxis_gridcolor=None,
        xmin=None, xmax=None, ymin=None, ymax=None, vmin=None, vmax=None, dv=None,
        overplot_keplerian_surface=False, keplerian_surface_kwargs=None,
        projection_x=False, projection_y=False, projection_z=True,
        show_colorbar=True, camera_eye_x=-1., camera_eye_y=-2., camera_eye_z=1.,
        show_figure=False, write_pdf=True, write_html=True, write_csv=False):
    """
    Make a three-dimensional position-position-velocity diagram.

    Args:
        path (str): Relative path to the FITS cube.
        path_to_mask (Optional[str]): Relative path to a second FITS cube to be
                used as a weighting function for the main cube data
        rms (Optional[float]): Clip the cube having cube.data > clip * rms
                If provided as None, taken as cube.rms
        clip (Optional[float]): Clip the cube having cube.data > clip * rms
        rmin (Optional[float]): Inner radius of the radial mask
        rmax (Optional[float]): Outer radius of the radial mask
        N (Optional[integer]): Downsample the data by a factor of N.
        cmin (Optional[float]): The lower bound of the velocity for the colorscale in km/s.
        cmax (Optional[float]): The upper bound of the velocity for the colorscale in km/s.
        constant_opacity (Optional[float]): If not None, use a constant opacity of the given value.
        ntrace (Optional[integer]): Number of opacity layers.
        markersize (Optional[integer]): Size of the marker in the PPV diagram.
        cmap (Optional[str]): Name of the colormap to use for the PPV diagram e.g., 'cmr.pride'
        hoverinfo (Optional[str]): Determines which trace information appear on hover.
                   Any combination of "x", "y", "z", "text", "name" joined with a "+"
                   or "all" or "none" or "skip". If `none` or `skip` are set, no
                   information is displayed upon hovering. But, if `none` is set,
                   click and hover events are still fired.
        xaxis_title (Optional[str]): X-axis title.
        yaxis_title (Optional[str]): Y-axis title.
        zaxis_title (Optional[str]): Z-axis title.
        xaxis_backgroundcolor (Optional[str]): X-axis background color.
        xaxis_gridcolor (Optional[str]): X-axis grid color.
        yaxis_backgroundcolor (Optional[str]): Y-axis background color.
        yaxis_gridcolor (Optional[str]): Y-axis grid color.
        zaxis_backgroundcolor (Optional[str]): Z-axis background color.
        zaxis_gridcolor (Optional[str]): Z-axis grid color.
        xmin (Optional[float]): The lower bound of PPV diagram X range.
        xmax (Optional[float]): The upper bound of PPV diagram X range.
        ymin (Optional[float]): The lower bound of PPV diagram Y range.
        ymax (Optional[float]): The upper bound of PPV diagram Y range.
        vmin (Optional[float]): The lower bound of PPV diagram Z range in km/s.
        vmax (Optional[float]): The upper bound of PPV diagram Z range in km/s.
        dv (Optional[float]): Desired velocity resolution in km/s.
        overplot_keplerian_surface (Optional[bool]): If True, overplot a projected
                Keplerian velocity profile onto PPV diagram as a 2D surface.
        keplerian_surface_kwargs (Optional[dict]): Arguments to pass to gofish
                self.keplerian() function for projected Keplerian velocity profile.
        projection_x (Optional[bool]): Whether or not to add projection on the Y-Z plane.
        projection_y (Optional[bool]): Whether or not to add projection on the X-Z plane.
        projection_z (Optional[bool]): Whether or not to add projection on the X-Y plane.
        show_colorbar (Optional[bool]): Whether or not to plot a colorbar.
        camera_eye_x (Optional[float]): The x component of the 'eye' camera vector.
        camera_eye_y (Optional[float]): The y component of the 'eye' camera vector.
        camera_eye_z (Optional[float]): The z component of the 'eye' camera vector.
        show_figure (Optional[bool]): If True, show PPV diagram.
        write_pdf (Optional[bool]): If True, write PPV diagram in a pdf file.
        write_html (Optional[bool]): If True, write PPV diagram in a html file.
        write_csv (Optional[bool]): If True, write the data to create the PPV diagram in a csv file.
    Returns:
        PPV diagram in a pdf and/or a html format.
    """
    # Read in the FITS data.
    cube = imagecube(path)
    cube.data = cube.data.astype(float)

    # Evaluate rms (not affected by custom weighting)
    rms = cube.rms if rms is None else rms

    # Apply custom weighting to the main FITS cube, e.g. to isolate non-Keplerian emission
    if path_to_mask is not None:
         cube_mask = imagecube(path_to_mask)
         cube_mask.data = cube_mask.data.astype(float)
         print('WARNING: Multiplying cube data with provided mask cube data.')
         cube.data *= cube_mask.data
         path = path.replace('.fits', '_weighted.fits')

    # Crop the data along the velocity axis, implemented from gofish
#    vmin = cube.velax[0] if vmin is None else vmin*1.0e3
#    vmax = cube.velax[-1] if vmax is None else vmax*1.0e3
    vmin = 0.5*(cube.velax.min() + cube.velax.max()) - 5.0e3 if vmin is None else vmin*1.0e3
    vmax = 0.5*(cube.velax.min() + cube.velax.max()) + 5.0e3 if vmax is None else vmax*1.0e3
    i = np.abs(cube.velax - vmin).argmin()
    i += 1 if cube.velax[i] < vmin else 0
    j = np.abs(cube.velax - vmax).argmin()
    j -= 1 if cube.velax[j] > vmax else 0
    cube.velax = cube.velax[i:j+1]
    cube.data = cube.data[i:j+1]

    if dv is not None:
        newvelax = np.arange(cube.velax[0], cube.velax[-1], dv*1.0e3)
        cs = CubicSpline(cube.velax, cube.data, axis=0)
        cube.data = cs(newvelax)
        cube.velax = newvelax

    # Generate a SNR mask
    print('Clipping data at threshold: ', clip * rms)
    mask_SNR = cube.data > clip * rms

    # Generate a radial mask
    r, t, z = cube.disk_coords()
    rmin = 0 if rmin is None else rmin
    rmax = cube.FOV/3. if rmax is None else rmax
    mask_r = np.logical_and(r >= rmin, r <= rmax)
    mask_r = np.tile(mask_r, (cube.data.shape[0], 1, 1))

    # Generate a combined mask
    mask = np.logical_and(mask_SNR, mask_r)

    # Masked LOS velocity, RA, Dec, intensity arrays.
    v = np.around((cube.velax[:, None, None] * np.ones(cube.data.shape))[mask]/1e3,decimals=3)
    x = np.around((cube.xaxis[None, None, :] * np.ones(cube.data.shape))[mask],decimals=3)
    y = np.around((cube.yaxis[None, :, None] * np.ones(cube.data.shape))[mask],decimals=3)
    i = np.around(cube.data[mask],decimals=3)

    # Take N random voxel.
    N = int(np.max([v.size/1.0e5,1])) if N is None else N # `np.int` was a deprecated alias for the builtin `int`
    if N > 1:
        idx = np.arange(v.size)
        np.random.shuffle(idx)
        v = v[idx][::N]
        x = x[idx][::N]
        y = y[idx][::N]
        i = i[idx][::N]

    if (v.shape[0] > 1.0e6):
        print("Warning: There are total", v.shape[0], "points to present. The output file can be very large! Consider using a smaller N.")

    # Normalize the intensity.
    i = (i - i.min())/(i.max() - i.min())

    # Determine the opacity of the data points.
    cuts = np.linspace(0, 1, ntrace+1)
    opacity = np.logspace(-1., 0.5, cuts.size - 1)
    if constant_opacity is not None:
        opacity[:] = constant_opacity
    datas = []

    xaxis_title = 'RA offset [arcsec]' if xaxis_title is None else xaxis_title
    yaxis_title = 'Dec offset [arcsec]' if yaxis_title is None else yaxis_title
    zaxis_title = 'velocity [km/s]' if zaxis_title is None else zaxis_title
    xaxis_backgroundcolor = 'white' if xaxis_backgroundcolor is None else xaxis_backgroundcolor
    xaxis_gridcolor = 'gray' if xaxis_gridcolor is None else xaxis_gridcolor
    yaxis_backgroundcolor = 'white' if yaxis_backgroundcolor is None else yaxis_backgroundcolor
    yaxis_gridcolor = 'gray' if yaxis_gridcolor is None else yaxis_gridcolor
    zaxis_backgroundcolor = 'white' if zaxis_backgroundcolor is None else zaxis_backgroundcolor
    zaxis_gridcolor = 'gray' if zaxis_gridcolor is None else zaxis_gridcolor
    xmin = cube.FOV/2.0 if xmin is None else xmin
    xmax = -cube.FOV/2.0 if xmax is None else xmax
    ymin = -cube.FOV/2.0 if ymin is None else ymin
    ymax = cube.FOV/2.0 if ymax is None else ymax

    if rmax is not None:
        xmin, xmax, ymin, ymax = rmax, -rmax, -rmax, rmax

    colorscale = make_colorscale(cmap) if colorscale is None else cmap
    cmin = vmin/1.0e3 if cmin is None else cmin
    cmax = vmax/1.0e3 if cmax is None else cmax

    # 3d scatter plot

    for a, alpha in enumerate(opacity):
        mask = np.logical_and(i >= cuts[a], i < cuts[a+1])
        datas += [go.Scatter3d(x=x[mask], y=y[mask], z=v[mask], mode='markers',
                               marker=dict(size=marker_size, color=v[mask], colorscale=colorscale,
                                           cauto=False, cmin=cmin, cmax=cmax,
                                           opacity=min(1.0, alpha)),
                               hoverinfo=hoverinfo,
#legendgroup="group1", name="SO", showlegend=True if a==0 else False,
#                              name='I ='+(str('% 4.2f' % cuts[a]))+' -'+(str('% 4.2f' % cuts[a+1]))
                              )
                 ]

    # layout
    layout = go.Layout(scene=dict(xaxis_title=xaxis_title,
                                  yaxis_title=yaxis_title,
                                  zaxis_title=zaxis_title,
                                  xaxis_backgroundcolor=xaxis_backgroundcolor,
                                  xaxis_gridcolor=xaxis_gridcolor,
                                  yaxis_backgroundcolor=yaxis_backgroundcolor,
                                  yaxis_gridcolor=yaxis_gridcolor,
                                  zaxis_backgroundcolor=zaxis_backgroundcolor,
                                  zaxis_gridcolor=zaxis_gridcolor,
                                  xaxis_range=[xmin, xmax],
                                  yaxis_range=[ymin, ymax],
                                  zaxis_range=[vmin/1.0e3, vmax/1.0e3],
                                  aspectmode='cube'),
#                       margin=dict(l=0, r=0, b=0, t=0),
                       margin=dict(l=0, r=0, b=0, t=0), showlegend=False,
                       )

    fig = go.Figure(data=datas, layout=layout)

    fig.update_traces(projection_x=dict(show=projection_x, opacity=1),
                      projection_y=dict(show=projection_y, opacity=1),
                      projection_z=dict(show=projection_z, opacity=1),
                     )

    if show_colorbar:
        fig.update_traces(marker_colorbar=dict(thickness=20,
#                                               tickvals=np.arange(cmin,cmax+1),
                                               tickformat='.1f',
                                               title='v [km/s]',
                                               title_side='right',
                                               len=0.5
                                              )
                         )
#        fig.update_layout(coloraxis_colorbar_x=-1.)

    if overplot_keplerian_surface:
        vkep   = cube.keplerian(**keplerian_surface_kwargs) / 1e3 # Convert m/s to km/s
        print("Overplotting projected Keplerian velocity profile as 2D surface. The output file can be very large!")
        fig.add_trace(go.Surface(z=vkep, x=cube.xaxis, y=cube.yaxis, opacity=1.0,
                                 colorscale=[[0,'gainsboro'], [1,'gainsboro']], showscale=False))

    camera = dict(up=dict(x=0, y=0, z=1),
                  center=dict(x=0, y=0, z=0),
                  eye=dict(x=camera_eye_x, y=camera_eye_y, z=camera_eye_z)
                 )

    fig.update_layout(scene_camera=camera)
    fig.update_layout(legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="left",
        x=0.01
    ))

    if show_figure:
        fig.show()
    if write_pdf:
        fig.write_image(path.replace('.fits', '_ppv.pdf'))
    if write_html:
        fig.write_html(path.replace('.fits', '_ppv.html'), include_plotlyjs=True)
    if write_csv:
        df = pd.DataFrame({"RA offset" : x, "Dec offset" : y, "velocity" : v})
        df.to_csv(path.replace('.fits', '_ppv.csv'), float_format='%.3e', index=False)
    return
