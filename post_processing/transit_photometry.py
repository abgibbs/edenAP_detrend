# -*- coding: utf-8 -*-
import numpy as np

import argparse
import shutil
import os
import pickle
import astropy.io.fits as pyfits
import matplotlib
# Force matplotlib to not use any Xwindows backend.
# matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.style.use('ggplot')

from scipy.signal import medfilt
from matplotlib import ticker

def CoordsToDecimal(coords, hours=False):
    if hours:
        hh,mm,ss = coords.split(':')
        decimal = np.float(hh) + (np.float(mm)/60.) + \
                  (np.float(ss)/3600.0)
        return decimal * (360./24.)

    ras = np.array([])
    decs = np.array([])
    for i in range(len(coords)):
        ra_string,dec_string = coords[i]
        # Get hour, minutes and secs from RA string:
        hh,mm,ss = ra_string.split(':')
        # Convert to decimal:
        ra_decimal = np.float(hh) + (np.float(mm)/60.) + \
                     (np.float(ss)/3600.0)
        # Convert to degrees:
        ras = np.append(ras,ra_decimal * (360./24.))
        # Now same thing for DEC:
        dd,mm,ss = dec_string.split(':')
        dec_decimal = np.abs(np.float(dd)) + (np.float(mm)/60.) + \
                      (np.float(ss)/3600.0)
        if dd[0] == '-':
            decs = np.append(decs,-1*dec_decimal)
        else:
            decs = np.append(decs,dec_decimal)
    return ras,decs

def get_super_comp(all_comp_fluxes, all_comp_fluxes_err):
   super_comp = np.zeros(all_comp_fluxes.shape[1])
   super_comp_err = np.zeros(all_comp_fluxes.shape[1])
   for i in range(all_comp_fluxes.shape[1]):
       data = all_comp_fluxes[:,i] 
       data_err = all_comp_fluxes_err[:,i]
       med_data = np.median(data)
       sigma = get_sigma(data)
       idx = np.where((data<med_data+5*sigma)&(data>med_data-5*sigma)&\
                      (~np.isnan(data))&(~np.isnan(data_err)))[0]
       super_comp[i] = np.median(data[idx])
       super_comp_err[i] = np.sqrt(np.sum(data_err[idx]**2)/np.double(len(data_err[idx])))
   return super_comp,super_comp_err

def get_sigma(data):
    mad = np.median(np.abs(data-np.median(data)))
    return mad*1.4826

def check_target(data,idx,min_ap,max_ap,force_aperture,forced_aperture, max_comp_dist = 15):
    distances = np.sqrt((data['data']['DEC_degs'][idx]-data['data']['DEC_degs'])**2 + \
                        (data['data']['RA_degs'][idx]-data['data']['RA_degs'])**2)
    idx_dist = np.argsort(distances)
    comp_dist = distances[idx_dist[1]]
    if comp_dist < max_comp_dist*(1./3600.):
        return False
    if not force_aperture:
        for chosen_aperture in min_ap,max_ap:
            try:
                target_flux = data['data']['star_'+str(idx)]['fluxes_'+str(chosen_aperture)+'_pix_ap']
                target_flux_err = data['data']['star_'+str(idx)]['fluxes_'+str(chosen_aperture)+'_pix_ap_err']
            except:
                target_flux = data['data']['target_star_'+str(idx)]['fluxes_'+str(chosen_aperture)+'_pix_ap']
                target_flux_err = data['data']['target_star_'+str(idx)]['fluxes_'+str(chosen_aperture)+'_pix_ap_err']
        nzero = np.where(target_flux<0)[0]
    if len(nzero)>0:
        return False
    else:
        chosen_aperture = forced_aperture
        try:
            target_flux = data['data']['star_'+str(idx)]['fluxes_'+str(chosen_aperture)+'_pix_ap']
            target_flux_err = data['data']['star_'+str(idx)]['fluxes_'+str(chosen_aperture)+'_pix_ap_err']
        except:
            target_flux = data['data']['target_star_'+str(idx)]['fluxes_'+str(chosen_aperture)+'_pix_ap']
            target_flux_err = data['data']['target_star_'+str(idx)]['fluxes_'+str(chosen_aperture)+'_pix_ap_err']
        nzero = np.where(target_flux<0)[0]
        if len(nzero)>0:
            return False
    return True

def super_comparison_detrend(data, idx, idx_comparison, chosen_aperture, 
                             comp_aperture=None, plot_comps=False, all_idx=None):

    if comp_aperture is None:
        comp_aperture = chosen_aperture

    try:
        target_flux = data['data']['star_'+str(idx)]['fluxes_'+str(chosen_aperture)+'_pix_ap'][all_idx]
        target_flux_err = data['data']['star_'+str(idx)]['fluxes_'+str(chosen_aperture)+'_pix_ap_err'][all_idx]
    except:
        target_flux = data['data']['target_star_'+str(idx)]['fluxes_'+str(chosen_aperture)+'_pix_ap'][all_idx]
        target_flux_err = data['data']['target_star_'+str(idx)]['fluxes_'+str(chosen_aperture)+'_pix_ap_err'][all_idx]
    if plot_comps:
        plt.plot(target_flux/np.median(target_flux),'b-')
    first_time = True
    for idx_c in idx_comparison:
        try:
            comp_flux = data['data']['star_'+str(idx_c)]['fluxes_'+str(comp_aperture)+'_pix_ap'][all_idx]
            comp_flux_err = data['data']['star_'+str(idx_c)]['fluxes_'+str(comp_aperture)+'_pix_ap_err'][all_idx]
        except:
            comp_flux = data['data']['target_star_'+str(idx_c)]['fluxes_'+str(comp_aperture)+'_pix_ap'][all_idx]
            comp_flux_err = data['data']['target_star_'+str(idx_c)]['fluxes_'+str(comp_aperture)+'_pix_ap_err'][all_idx]
        if first_time:
            comp_med = np.median(comp_flux)
            all_comp_fluxes = comp_flux/comp_med
            all_comp_fluxes_err = comp_flux_err/comp_med
            first_time = False
        else:
            comp_med = np.median(comp_flux)
            all_comp_fluxes = np.vstack((all_comp_fluxes,comp_flux/comp_med))
            all_comp_fluxes_err = np.vstack((all_comp_fluxes_err,comp_flux_err/comp_med))
        if plot_comps:
            plt.plot(comp_flux/comp_med,'r-',alpha=0.1)
    super_comp,super_comp_err = get_super_comp(all_comp_fluxes,all_comp_fluxes_err)
    if plot_comps:
        plt.plot(super_comp,'r-')
        plt.show()
    relative_flux = target_flux/super_comp
    relative_flux_err = np.sqrt( (super_comp_err*target_flux/super_comp**2)**2 + \
                                 (target_flux_err/super_comp)**2)
    med_rel_flux = np.median(relative_flux)
    return relative_flux/med_rel_flux,relative_flux_err/med_rel_flux

def save_photometry(t, rf, rf_err, output_folder, target_name, plot_data=False, title=''):
    rf_mag = -2.5*np.log10(rf)
    rf_mag_err = rf_err*2.5/(np.log(10)*rf)
    f = open(output_folder + target_name + '.dat','w')
    f2 = open(output_folder + target_name + '_norm_flux.dat','w')
    f.write('# Times (BJD) \t Diff. Mag. \t Diff. Mag. Err.\n')
    f2.write('# Times (BJD) \t Norm. Flux. \t Norm. Flux Err.\n')
    for i in range(len(t)):
        if not np.isnan(rf_mag[i]) and not np.isnan(rf_mag_err[i]):
            f.write(str(t[i])+'\t'+str(rf_mag[i])+'\t'+str(rf_mag_err[i])+'\n')
            f2.write(str(t[i])+'\t'+str(rf[i])+'\t'+str(rf_err[i])+'\n')
    f.close()
    if plot_data:
        # Bin on a n-point window:
        t_min = np.min(t)
        t_hours = (t - t_min) * 24.
        n_bin = 10
        times_bins = []
        fluxes_bins = []
        errors_bins = []
        for i in range(0,len(t),n_bin):
            times_bins.append(np.median(t_hours[i:i+n_bin-1]))
            fluxes_bins.append(np.median(rf[i:i+n_bin-1]))
            errors_bins.append(np.sqrt(np.sum(rf_err[i:i+n_bin-1]**2))/np.double(n_bin))
        
        # Calculate standard deviation of median filtered data
        mfilt = median_filter(rf)
        sigma = get_sigma(rf-mfilt)
        sigma_mag = -2.5*np.log10((1.-sigma)/1.)
        # Make plot
        fig = plt.figure()
        plt.errorbar(t_hours,rf,rf_err,fmt='o',alpha=0.3,label='Data')
        plt.errorbar(np.array(times_bins),np.array(fluxes_bins),np.array(errors_bins),fmt='o',label='Binned data')
        plt.annotate('$\sigma_{{m}}$ = {:.0f} ppm = {:.1f} mmag'.format(sigma*1e6, sigma_mag*1e3), 
                     xy=(0.5, 0.05), xycoords='axes fraction', va='bottom', ha='center')
        plt.xlabel('Time from start (hr)')
        plt.ylabel('Relative flux')
        plt.title(title,fontsize='12')
        plt.xlim(-0.05*np.ptp(t_hours), 1.05*np.ptp(t_hours))
        nom_ymin = 0.95
        data_min = np.percentile(rf-rf_err, 1)
        nom_ymax = 1.05
        data_max = np.percentile(rf+rf_err, 99)
        plt.ylim(np.max([nom_ymin, data_min]), np.min([nom_ymax, data_max]))
        x_formatter = ticker.ScalarFormatter(useOffset=False)
        plt.gca().xaxis.set_major_formatter(x_formatter)
        plt.legend()
        plt.savefig(output_folder+target_name+'.pdf')
        plt.close()

def save_photometry_hs(data, idx, idx_comparison, 
                       chosen_aperture, min_aperture, max_aperture,
                       idx_sort_times, output_folder, target_name, 
                       band='i', all_idx=None):
    # Define string formatting:
    header_fmt = '#{0:<31} {1:<16} {2:<16} {3:<8} {4:<8} ' + \
                 '{5:<8} {6:<8} {7:<8} {8:<8} ' + \
                 '{9:<8} {10:<8} {11:<8} {12:<8} ' + \
                 '{13:<8} {14:<8} {15:<8} {16:<8} ' + \
                 '{17:<8} {18:<8} {19:<8}\n'
    header = header_fmt.format(
             'frame', 'BJD', 'JD', 'mag1', 'mag1_err', 
             'mag2', 'mag2_err', 'mag3', 'mag3_err', 
             'rmag1', 'rmag2', 'rmag3', 'cen_x', 
             'cen_y', 'bg', 'bg_err', 'FWHM', 
             'HA', 'ZA', 'Z')
    s = '{0:<32} {1:<16.8f} {2:<16.8f} {3:< 8.4f} {4:<8.4f} ' + \
        '{5:< 8.4f} {6:<8.4f} {7:< 8.4f} {8:<8.4f} ' + \
        '{9:< 8.4f} {10:< 8.4f} {11:< 8.4f} {12:<8.3f} ' + \
        '{13:<8.3f} {14:<8.3f} {15:<8.3f} {16:< 8.3f} ' + \
        '{17:< 8.2f} {18:<8.2f} {19:<8.2f}\n'

    all_ids = []
    all_ras = []
    all_decs = []
    all_mags = []
    all_rms = []

    hs_folder = output_folder+'LC/'
    # Create folder for the outputs in HS format:
    if not os.path.exists(hs_folder):
        os.mkdir(hs_folder)

    # First, write lightcurve in the HS format for each star. First the comparisons:
    print ('Saving data for target and', len(idx_comparison), 'comparison stars')
    for i in idx_comparison+[idx]:
        try:
            d = data['data']['star_'+str(i)]
        except:
            d = data['data']['target_star_'+str(i)]
        if i==idx:
            star_name=target_name
        else:
            star_name = str(data['data']['IDs'][i])
        ra = data['data']['RA_degs'][i]
        dec = data['data']['DEC_degs'][i]
        all_ids.append(star_name)
        all_ras.append(ra)
        all_decs.append(dec)
        all_mags.append(np.median(-2.512*np.log10(d['fluxes_'+str(chosen_aperture)+'_pix_ap'][all_idx])))
        mag = data['data']['Jmag'][i]
        f = open(str(hs_folder+star_name+'.epdlc'),'w')
        f.write(header)
        # Get super-comparison detrend for the current star:
        current_comps = []
        for ii in idx_comparison:
            if ii != i:
               current_comps.append(ii)

        r_flux1, r_flux_err1 = super_comparison_detrend(data, i, current_comps, chosen_aperture, comp_aperture=chosen_aperture, plot_comps=False, all_idx=all_idx)
        r_flux2, r_flux_err2 = super_comparison_detrend(data, i, current_comps, min_aperture, comp_aperture=chosen_aperture, plot_comps=False, all_idx=all_idx)
        r_flux3, r_flux_err3 = super_comparison_detrend(data, i, current_comps, max_aperture, comp_aperture=chosen_aperture, plot_comps=False, all_idx=all_idx)

        rmag1 = -2.512*np.log10(r_flux1)
        rmag2 = -2.512*np.log10(r_flux2)
        rmag3 = -2.512*np.log10(r_flux3)

        idx_not_nan = np.where(~np.isnan(rmag1))[0]
        all_rms.append(np.sqrt(np.var(rmag1[idx_not_nan])))

        for j in idx_sort_times:
            if (not np.isnan(rmag1[j])) and (not np.isnan(rmag2[j])) and (not np.isnan(rmag3[j])):
                # Get magnitudes and errors:
                mag1 = -2.512*np.log10(d['fluxes_'+str(chosen_aperture)+'_pix_ap'][all_idx][j])
                mag1_err = (2.512*d['fluxes_'+str(chosen_aperture)+'_pix_ap_err'][all_idx][j])/(np.log(10.)*d['fluxes_'+str(chosen_aperture)+'_pix_ap'][all_idx][j])
                mag2 = -2.512*np.log10(d['fluxes_'+str(min_aperture)+'_pix_ap'][all_idx][j])
                mag2_err = (2.512*(d['fluxes_'+str(min_aperture)+'_pix_ap_err'][all_idx][j]))/(np.log(10.)*d['fluxes_'+str(min_aperture)+'_pix_ap'][all_idx][j])
                mag3 = -2.512*np.log10(d['fluxes_'+str(max_aperture)+'_pix_ap'][all_idx][j])
                mag3_err = (2.512*(d['fluxes_'+str(max_aperture)+'_pix_ap_err'][all_idx][j]))/(np.log(10.)*d['fluxes_'+str(max_aperture)+'_pix_ap'][all_idx][j])

                if d['fwhm'][all_idx][j] != 0.:
                    FWHM = d['fwhm'][all_idx][j]
                else:
                    FWHM = -1
                lst_deg = CoordsToDecimal(data['LST'][all_idx][j], hours = True)
                HA = lst_deg-ra
                ZA = np.arccos(1./float(data['airmasses'][all_idx][j]))*(180./np.pi)
                Z = float(data['airmasses'][all_idx][j])
                
                entries = [data['frame_name'][all_idx][j].split('/')[-1], data['BJD_times'][all_idx][j], data['JD_times'][all_idx][j],
                           mag1, mag1_err, mag2, mag2_err, mag3, mag3_err, 
                           rmag1[j], rmag2[j], rmag3[j], d['centroids_x'][all_idx][j], 
                           d['centroids_y'][all_idx][j], d['background'][all_idx][j], d['background_err'][all_idx][j], FWHM, 
                           HA, ZA, Z]
                f.write(s.format(*entries))
        f.close()

def plot_images(data, idx, idx_comparison, aperture, min_ap, max_ap, 
                out_dir, frames, idx_frames, half_size=50, overwrite=False):
    def plot_im(d, cen_x, cen_y, obj_x, obj_y, half_size, frame_name, object_name, overwrite):
        if not os.path.exists(out_dir+'sub_imgs/'+object_name):
            os.makedirs(out_dir+'sub_imgs/'+object_name)
        fname = '{:}/sub_imgs/{:}/{:}_{:}.png'.format(
                 out_dir, object_name, frame_name.split('/')[-1], object_name)
        if not os.path.exists(fname) or overwrite:
            # Plot image of the target:
            fig = plt.figure()
            x0 = np.max([0,int(cen_x)-half_size])
            x1 = np.min([int(cen_x)+half_size,d.shape[1]])
            y0 = np.max([0,int(cen_y)-half_size])
            y1 = np.min([int(cen_y)+half_size,d.shape[0]])
            subimg = np.copy(d[y0:y1,x0:x1])
            subimg = subimg - np.median(subimg)
            x_cen = obj_x - x0
            y_cen = obj_y - y0
            im = plt.imshow(subimg)
            im.set_clim(0, 1000)
            plt.plot(x_cen, y_cen, 'wx', markersize=15, alpha=0.5)
            circle = plt.Circle((x_cen, y_cen), min_ap, color='black', fill=False)
            circle2 = plt.Circle((x_cen ,y_cen), max_ap, color='black', fill=False)
            circle3 = plt.Circle((x_cen, y_cen), aperture, color='white', fill=False)
            plt.gca().add_artist(circle)
            plt.gca().add_artist(circle2)
            plt.gca().add_artist(circle3)
            plt.savefig(fname)
            plt.close()
            if object_name=='target':
                print (frame_name)
                print ('Max flux:',np.max(subimg))
                print ('Centroid:',cen_x, cen_y)
        
    # Get the centroids of the target:
    try:
        target_cen_x = data['data']['star_'+str(idx)]['centroids_x'][idx_frames]
        target_cen_y = data['data']['star_'+str(idx)]['centroids_y'][idx_frames]
        print ('Target:','star_'+str(idx))
    except:
        target_cen_x = data['data']['target_star_'+str(idx)]['centroids_x'][idx_frames]
        target_cen_y = data['data']['target_star_'+str(idx)]['centroids_y'][idx_frames]
        print ('Target:','target_star_'+str(idx))

#         print (target_cen_x)
#         print (target_cen_y)

    # Same for the comparison stars:
    for i in range(len(idx_comparison)):
        idx_c = idx_comparison[i]
        try:
            comp_cen_x = data['data']['star_'+str(idx_c)]['centroids_x'][idx_frames]
            comp_cen_y = data['data']['star_'+str(idx_c)]['centroids_y'][idx_frames]
        except:
            comp_cen_x = data['data']['target_star_'+str(idx_c)]['centroids_x'][idx_frames]
            comp_cen_y = data['data']['target_star_'+str(idx_c)]['centroids_y'][idx_frames]
        if i==0:
            all_comp_cen_x = comp_cen_x
            all_comp_cen_y = comp_cen_y
        else:
            all_comp_cen_x = np.vstack((all_comp_cen_x,comp_cen_x)) 
            all_comp_cen_y = np.vstack((all_comp_cen_y,comp_cen_y))

    # Now plot images around centroids plus annulus:
    exts = np.unique(data['data']['ext']).astype('int')
    nframes = len(frames)
    for i in range(nframes):
        for ext in exts:
            d = pyfits.getdata(frames[i], ext=ext)
            idx_names = np.where(data['data']['ext']==ext)
            names_ext = data['data']['names'][idx_names]
            for name in names_ext:
                if 'target' in name:
                    # Plot image of the target:
                    plot_im(d, target_cen_x[0], target_cen_y[0],
                            target_cen_x[i], target_cen_y[i],
                            half_size, frames[i],'target', overwrite)
            # Plot image of the comparisons:
            for j in range(len(idx_comparison)):
                idx_c = idx_comparison[j]
                name = 'star_'+str(idx_c)
                if name in names_ext:
                    plot_im(d, all_comp_cen_x[j,0], all_comp_cen_y[j,0], 
                            all_comp_cen_x[j,i], all_comp_cen_y[j,i], 
                            half_size, frames[i],name, overwrite)

def plot_cmd(colors, data, idx_target, idx_comparison, post_dir):
    """
    Plot the color-magnitude diagram of all stars, 
    indicating the target and selected comparison stars.
    """
    ms = plt.rcParams['lines.markersize']
    fig = plt.figure()
    plt.plot(colors,data['data']['Jmag'],'b.', label='All stars')
    plt.plot(colors[idx],data['data']['Jmag'][idx],'ro',ms=ms*2, label='Target')
    plt.plot(colors[idx_comparison],data['data']['Jmag'][idx_comparison],'r.', label='Selected comparisons')
    plt.title('Color-magnitude diagram of stars')
    plt.xlabel('J$-$H color')
    plt.ylabel('J (mag)')
    plt.legend(loc='best')
    plt.gca().invert_yaxis()
    plt.savefig(post_dir+'CMD.pdf')
    plt.close()

def median_filter(arr):
    median_window = int(np.sqrt(len(arr)))
    if median_window%2==0:
        median_window += 1
    return medfilt(arr, median_window)

################ INPUT DATA #####################

parser = argparse.ArgumentParser()
parser.add_argument('-telescope',default=None)
parser.add_argument('-datafolder',default=None)
parser.add_argument('-target_name',default=None)
parser.add_argument('-ra',default=None)
parser.add_argument('-dec',default=None)
parser.add_argument('-band',default='ip')
parser.add_argument('-dome',default='')
parser.add_argument('-minap',default = 5)
parser.add_argument('-maxap',default = 25)
parser.add_argument('-apstep',default = 1)
parser.add_argument('-ncomp',default = 10)
parser.add_argument('-forced_aperture',default = 15)
parser.add_argument('--force_aperture', dest='force_aperture', action='store_true')
parser.set_defaults(force_aperture=False)
parser.add_argument('--autosaveLC', dest='autosaveLC', action='store_true')
parser.set_defaults(autosaveLC=False)
parser.add_argument('--plt_images', dest='plt_images', action='store_true')
parser.set_defaults(plt_images=False)
parser.add_argument('--all_plots', dest='all_plots', action='store_true')
parser.set_defaults(all_plots=False)
parser.add_argument('--overwrite', dest='overwrite', action='store_true')
parser.set_defaults(overwrite=False)

args = parser.parse_args()

force_aperture = args.force_aperture
autosaveLC = args.autosaveLC
plt_images = args.plt_images
all_plots = args.all_plots
overwrite = args.overwrite
telescope = args.telescope
target_name = args.target_name
telescope = args.telescope
date = args.datafolder
band = args.band
dome = args.dome

# Check for which telescope the user whishes to download data from:
ftelescopes = open('../userdata.dat','r')
while True:
    line = ftelescopes.readline()
    if line != '':
        if line[0] != '#':
            cp,cf = line.split()
            cp = cp.split()[0]
            cf = cf.split()[0]
            if telescope.lower() == cp.lower():
                break
    else:
        print ('\t > Telescope '+telescope+' is not on the list of saved telescopes. ')
        print ('\t   Please associate it on the userdata.dat file.')

if telescope == 'SWOPE':
    foldername = cf + telescope+'/red/'+date+'/'+target_name+'/'
elif telescope == 'CHAT':
    foldername = cf + 'red/'+date+'/'+target_name+'-'+band+'/'
else:
    foldername = cf +'red/'+date+'/'+target_name+'-'+band+'/'

post_dir = foldername+'post_processing/'
if not os.path.exists(post_dir):
    os.mkdir(post_dir)

filename = 'photometry.pkl'
target_coords = [[args.ra,args.dec.split()[0]]]
min_ap = int(args.minap)
max_ap = int(args.maxap)
forced_aperture = int(args.forced_aperture)
ncomp = int(args.ncomp)
#################################################

# Convert target coordinates to degrees:
target_ra,target_dec = CoordsToDecimal(target_coords)

# Open dictionary, save times:
data = pickle.load(open(foldername+filename,'rb'))
all_sites = len(data['frame_name'])*[[]]
all_cameras = len(data['frame_name'])*[[]]

for i in range(len(data['frame_name'])):
    frames = data['frame_name'][i]
    d,h = pyfits.getdata(frames,header=True)
    try:
        if h['SITE'] != '' and h['INSTRUME'] != '':
            all_cameras[i] = 'sinistro'
            #if h['INSTRUME'] in ['fl03','fl04','fl02','fl06']:
            #    all_cameras[i] = 'sinistro'
            #else:
            #    all_cameras[i] = 'sbig'
            all_sites[i] = h['SITE']
        else:
            all_sites[i] = telescope 
            all_cameras[i] = h['INSTRUME']
    except:
        all_sites[i] = telescope
        all_cameras[i] = 'VATT4k'

sites = []
frames_from_site = {}
for i in range(len(all_sites)):
    s = all_sites[i]
    c = all_cameras[i]
    if s+'+'+c not in sites:
        sites.append(s+'+'+c)
        frames_from_site[s+'+'+c] = [i]
    else:
        frames_from_site[s+'+'+c].append(i)

print ('Observations taken from: ',sites)

# Get all the RAs and DECs of the objects:
all_ras,all_decs = data['data']['RA_degs'],data['data']['DEC_degs']
# Search for the target:
distance = np.sqrt((all_ras-target_ra)**2 + (all_decs-target_dec)**2)
idx = (np.where(distance == np.min(distance))[0])[0]
# Search for closest stars in color to target star:
target_hmag,target_jmag = data['data']['Hmag'][idx],data['data']['Jmag'][idx]
colors = data['data']['Jmag']-data['data']['Hmag']
target_color = target_hmag-target_jmag
distance = np.sqrt((colors-target_color)**2. + (target_jmag-data['data']['Jmag'])**2.)
idx_distances = np.argsort(distance)
idx_comparison = []
# Select brightest stars whithin 2.5 of the targets star flux first:
for i in idx_distances:
    if i != idx:
        if check_target(data,i,min_ap,max_ap,force_aperture,forced_aperture) and target_jmag>data['data']['Jmag'][i] and \
                        np.abs(target_jmag - data['data']['Jmag'][i]) < 2.:
            idx_comparison.append(i)
    if len(idx_comparison)==ncomp:
        break

# Now select the faint end:
for i in idx_distances:
    if (i != idx) and (i not in idx_comparison):
        if check_target(data,i,min_ap,max_ap,force_aperture,forced_aperture):
            idx_comparison.append(i)
    if len(idx_comparison)==ncomp:
        break

# Plot the color-magnitude diagram
plot_cmd(colors, data, idx, idx_comparison, post_dir)

print ('\t',len(idx_comparison),' comparison stars!')
for site in sites:
    print ('\t Photometry for site:',site)
    idx_frames = frames_from_site[site]
    times = data['BJD_times'][idx_frames]
    idx_sort_times = np.argsort(times)
    cam = (site.split('+')[-1]).split('-')[-1]
    print ('\t Frames:',data['frame_name'][idx_frames])
    # Check which is the aperture that gives a minimum rms:
    if force_aperture:
        print ('\t Forced aperture to ',forced_aperture)
        chosen_aperture = forced_aperture
    else:
        print ('\t Estimating optimal aperture...')
        apertures_to_check = range(min_ap,max_ap)
        precision = np.zeros(len(apertures_to_check))

        if not os.path.exists(post_dir+'post_processing_outputs/'):
            os.mkdir(post_dir+'post_processing_outputs/')

        for i in range(len(apertures_to_check)):
            aperture = apertures_to_check[i]
            # Check the target
            relative_flux, relative_flux_err = super_comparison_detrend(data, idx, idx_comparison, aperture, all_idx = idx_frames)
            save_photometry(times[idx_sort_times], relative_flux[idx_sort_times], relative_flux_err[idx_sort_times],
                            post_dir+'post_processing_outputs/', target_name='photometry_ap'+str(aperture)+'_pix',
                            plot_data=True)
            mfilt = median_filter(relative_flux[idx_sort_times])
            precision[i] = get_sigma((relative_flux[idx_sort_times] - mfilt)*1e6)

        idx_max_prec = np.argmin(precision)
        chosen_aperture = apertures_to_check[idx_max_prec]
        print ('\t >> Best precision achieved at an aperture of ',chosen_aperture,'pixels')
        print ('\t >> Precision achieved: {:.0f} ppm'.format(precision[idx_max_prec]))
        # And while we're at it, check the comparisons too
        if not os.path.exists(post_dir+'comp_light_curves/'):
            os.mkdir(post_dir+'comp_light_curves/')
        idx_comps = np.array(idx_comparison)
        for i_c in idx_comps:
            idx_c = idx_comps[np.where(idx_comps!=i_c)]
            rf_comp, rf_comp_err = super_comparison_detrend(data, i_c, idx_c, chosen_aperture, all_idx = idx_frames)
            save_photometry(times[idx_sort_times], rf_comp[idx_sort_times], rf_comp_err[idx_sort_times],
                            post_dir+'comp_light_curves/', target_name='star_{:}_photometry_ap{:}_pix'.format(i_c, chosen_aperture),
                            plot_data=True)

    # Saving sub-images
    if plt_images:
        plot_images(data, idx, idx_comparison, chosen_aperture, min_ap, max_ap, 
                    post_dir, data['frame_name'][idx_frames], idx_frames, overwrite=overwrite)

    # Save and plot final LCs:
    print ('\t Getting final relative flux...')
    relative_flux,relative_flux_err = super_comparison_detrend(data,idx,idx_comparison,chosen_aperture,plot_comps = all_plots,all_idx = idx_frames)
    median_flux = np.max([np.median(relative_flux[idx_sort_times][0:10]),np.median(relative_flux[idx_sort_times][-10:])])
    print ('\t Saving...')
    save_photometry(times[idx_sort_times],relative_flux[idx_sort_times]/median_flux,relative_flux_err[idx_sort_times]/median_flux,\
                    post_dir,target_name = target_name,plot_data = True, title = target_name + ' on ' + foldername.split('/')[-3]+' at '+site)

    save_photometry_hs(data,idx,idx_comparison,chosen_aperture,min_ap,max_ap,idx_sort_times,post_dir,target_name,band = band,all_idx = idx_frames)

    print ('\t Done!\n')
    
    # Not sure why these files are copied...
    os.makedirs(post_dir+date+'/'+target_name+'/'+band+'/LC/', exist_ok=True)
    src_files = os.listdir(post_dir+'/LC/')
    for file_name in src_files:
        shutil.copy2(os.path.join(post_dir+'LC/',file_name),post_dir+'/'+date+'/'+target_name+'/'+band+'/LC/')
    print ('\t Done!\n')
    plt.clf()
