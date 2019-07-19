#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 20 16:41:47 2018

@author: Thomas Bury

Code to simulate the RM model and compute EWS

"""

# import python libraries
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# import EWS function
import sys
sys.path.append('../../early_warnings')
from ews_compute import ews_compute


#---------------------
# Directory for data output
#–----------------------

# Name of directory within data_export
dir_name = 'fold_ews_temp'

if not os.path.exists('data_export/'+dir_name):
    os.makedirs('data_export/'+dir_name)


#--------------------------------
# Global parameters
#–-----------------------------


# Simulation parameters
dt = 0.01
t0 = 0
tmax = 500
tburn = 100 # burn-in period
numSims = 1
seed = 2 # random number generation seed

# EWS parameters
dt2 = 1 # spacing between time-series for EWS computation
rw = 0.4 # rolling window
bw = 0.1 # bandwidth
lags = [1,2,3] # autocorrelation lag times
ews = ['var','ac','sd','cv','skew','kurt','smax','aic','cf'] # EWS to compute
ham_length = 40 # number of data points in Hamming window
ham_offset = 0.5 # proportion of Hamming window to offset by upon each iteration
pspec_roll_offset = 20 # offset for rolling window when doing spectrum metrics


#----------------------------------
# Simulate many (transient) realisations
#----------------------------------

# Model (bound system by using a piecewise definition)
def de_fun(x,u):
    output = -u - x**2 if x > -1.5 else 0
    return output
    
# Model parameters
sigma = 0.1 # noise intensity
bl = -1 # control parameter initial value
bh = 0.2 # control parameter final value
bcrit = 0 # bifurcation point (computed in Mathematica)
x0 = np.sqrt(-bl) # intial condition (equilibrium value)


# Initialise arrays to store single time-series data
t = np.arange(t0,tmax,dt)
x = np.zeros(len(t))
y = np.zeros(len(t))

# Set up bifurcation parameter b, that increases linearly in time from bl to bh
b = pd.Series(np.linspace(bl,bh,len(t)),index=t)
# Time at which bifurcation occurs
tbif = b[b > bcrit].index[1]


## Implement Euler Maryuyama for stocahstic simulation

# Set seed
np.random.seed(seed)

# Initialise a list to collect trajectories
list_traj_append = []

# loop over simulations
print('\nBegin simulations \n')
for j in range(numSims):
    
    
    # Create brownian increments (s.d. sqrt(dt))
    dW_x_burn = np.random.normal(loc=0, scale=sigma*np.sqrt(dt), size = int(tburn/dt))
    dW_x = np.random.normal(loc=0, scale=sigma*np.sqrt(dt), size = len(t))
        
    # Run burn-in period on x0
    for i in range(int(tburn/dt)):
        x0 = x0 + de_fun(x0,bl)*dt + dW_x_burn[i]
        
    # Initial condition post burn-in period
    x[0]=x0
    
    # Run simulation
    for i in range(len(t)-1):
        x[i+1] = x[i] + de_fun(x[i],b.iloc[i])*dt + dW_x[i]
            
    # Store series data in a temporary DataFrame
    data = {'Realisation number': (j+1)*np.ones(len(t)),
                'Time': t,
                'x': x}
    df_temp = pd.DataFrame(data)
    # Append to list
    list_traj_append.append(df_temp)
    
    print('Simulation '+str(j+1)+' complete')

#  Concatenate DataFrame from each realisation
df_traj = pd.concat(list_traj_append)
df_traj.set_index(['Realisation number','Time'], inplace=True)


#----------------------
## Execute ews_compute for each realisation in x and y
#---------------------

# Filter time-series to have time-spacing dt2
df_traj_filt = df_traj.loc[::int(dt2/dt)]

# set up a list to store output dataframes from ews_compute- we will concatenate them at the end
appended_ews = []
appended_pspec = []
appended_ktau = []

# loop through realisation number
print('\nBegin EWS computation\n')
for i in range(numSims):
    # loop through variable
    for var in ['x']:
        
        ews_dic = ews_compute(df_traj_filt.loc[i+1][var], 
                          roll_window = rw, 
                          band_width = bw,
                          lag_times = lags, 
                          ews = ews,
                          ham_length = ham_length,
                          ham_offset = ham_offset,
                          pspec_roll_offset = pspec_roll_offset,
                          upto=tbif)
        
        # The DataFrame of EWS
        df_ews_temp = ews_dic['EWS metrics']
        # The DataFrame of power spectra
        df_pspec_temp = ews_dic['Power spectrum']
        # The DataFrame of Kendall tau values
        df_ktau_temp = ews_dic['Kendall tau']
        
        # Include a column in the DataFrames for realisation number and variable
        df_ews_temp['Realisation number'] = i+1
        df_ews_temp['Variable'] = var
        
        df_pspec_temp['Realisation number'] = i+1
        df_pspec_temp['Variable'] = var
        
        df_ktau_temp['Realisation number'] = i+1
        df_ktau_temp['Variable'] = var
                
        # Add DataFrames to list
        appended_ews.append(df_ews_temp)
        appended_pspec.append(df_pspec_temp)
        appended_ktau.append(df_ktau_temp)
        
    # Print status every realisation
    if np.remainder(i+1,1)==0:
        print('EWS for realisation '+str(i+1)+' complete')


# Concatenate EWS DataFrames. Index [Realisation number, Variable, Time]
df_ews = pd.concat(appended_ews).reset_index().set_index(['Realisation number','Variable','Time'])
# Concatenate power spectrum DataFrames. Index [Realisation number, Variable, Time, Frequency]
df_pspec = pd.concat(appended_pspec).reset_index().set_index(['Realisation number','Variable','Time','Frequency'])
# Concatenate Kendall tau DataFrames
df_ktau = pd.concat(appended_ktau).set_index('Realisation number','Variable')




#-------------------------
# Plots to visualise EWS
#-------------------------

# Realisation number to plot
plot_num = 1
var = 'x'
## Plot of trajectory, smoothing and EWS of var (x or y)
fig1, axes = plt.subplots(nrows=4, ncols=1, sharex=True, figsize=(6,6))
df_ews.loc[plot_num,var][['State variable','Smoothing']].plot(ax=axes[0],
          title='Early warning signals for a single realisation',
          ylim=[-1,1.5])
df_ews.loc[plot_num,var]['Variance'].plot(ax=axes[1],legend=True)
df_ews.loc[plot_num,var][['Lag-1 AC','Lag-2 AC','Lag-3 AC']].plot(ax=axes[1], secondary_y=True,legend=True)
df_ews.loc[plot_num,var]['Smax'].dropna().plot(ax=axes[2],legend=True)
df_ews.loc[plot_num,var][['AIC fold','AIC hopf','AIC null']].dropna().plot(ax=axes[3],legend=True)


## Define function to make grid plot for evolution of the power spectrum in time
def plot_pspec_grid(tVals, plot_num, var):
    '''
    Inputs:
        tVals: the time values at which to display the power spectrum
        plot_num: the realisation number to use
        var: the state varialbe to use
    
    Output: a grid plot of the power spectra and their best fits
    '''
    
    g = sns.FacetGrid(df_pspec.loc[plot_num,var].loc[t_display].reset_index(), 
                  col='Time',
                  col_wrap=3,
                  sharey=False,
                  aspect=1.5,
                  size=1.8
                  )

    g.map(plt.plot, 'Frequency', 'Empirical', color='k', linewidth=2)
    g.map(plt.plot, 'Frequency', 'Fit fold', color='b', linestyle='dashed', linewidth=1)
    g.map(plt.plot, 'Frequency', 'Fit hopf', color='r', linestyle='dashed', linewidth=1)
    g.map(plt.plot, 'Frequency', 'Fit null', color='g', linestyle='dashed', linewidth=1)
    # Axes properties 
    axes = g.axes
    # Set y labels
    for ax in axes[::3]:
        ax.set_ylabel('Power')
        # Set y limit as max power over all time
        for ax in axes:
            ax.set_ylim(top=1.05*max(df_pspec.loc[plot_num,var]['Empirical']), bottom=0)
    return g

#  Choose time values at which to display power spectrum
t_display = df_pspec.index.levels[2][::1].values

plot_pspec_x = plot_pspec_grid(t_display,1,'x')





#------------------------------------
## Export data / figures
#-----------------------------------

# Export power spectrum evolution (grid plot)
plot_pspec_x.savefig('figures/pspec_evol_fold.png', dpi=200)

## Export the first 5 realisations to see individual behaviour
# EWS DataFrame (includes trajectories)
df_ews.loc[:5].to_csv('data_export/'+dir_name+'/ews_singles.csv')
# Power spectrum DataFrame (only empirical values)
df_pspec.loc[:5,'Empirical'].dropna().to_csv('data_export/'+dir_name+'/pspecs.csv',
            header=True)









