'''
Import necessary packages
'''
import numpy as np
import scipy
import scipy.integrate
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib
import pickle

#set figure font sizes for readability
font = {'size' : 30,
       'family': 'serif',
       'sans-serif': ['Helvetica']}
matplotlib.rc('font', **font)
matplotlib.rc('text', usetex=True)
color_cycle = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
               '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']




'''
#############################

Initiate parameter values

#############################
'''


init_param_dict = {
 
    #----------------------------
    #Glutamate -> GPCR parameters
    #----------------------------
     
    #G <-> G*
    'kp': 0.03, #activation rate
    'km': 0.04, #inactivation rate

    #G* -> Gd1 -> G
    'kd1': 0.01, #homologous (Gd1) deactivation rate
    'kr1': 0.005, #0.003 #homologous reactivation rate
    #G -> Gd2 -> G
    'kd2': 0.003, #0.0025 #heterologous (Gd2) deactivation rate
    'kr2': 0.0007, #0.0004 #heterologous reactivation rate



    #-------------------------------
    #IP3 -> Ca2+ dynamics parameters
    #-------------------------------

    'gamma': 5.4054, #(cyt vol) / (ER vol)

    #----------
    #Internal (Cytosol/ER)
    #----------
    #IP3R channel (Ca2+ ER -> Ca2+ Cyt)
    'v_ip3r': 0.222, #max IP3R channel flux 

    #Li-Rinzel parameters for IP3R channel
    'd1': 0.13,
    'd2': 1.049,
    'd3': 0.9434,
    'd5': 0.08234,
    'a2': 0.04,

    #SERCA pump (Ca2+ Cyt -> Ca2+ ER)
    'v_serca': 0.9, #max SERCA flux
    'k_serca': 0.1, #half-saturation of Ca2+ for SERCA

    #Leak (Ca2+ ER <-> Ca2+ Cyt)
    'v_er_leak': 0.002, #concentration gradient leak

    #----------
    #External (Cytosol/Extracellular)
    #----------
    #Leak (Ca2+ Extracellular <-> Ca2+ Cyt)
    'v_in': 0.05, #constant inward leak (extra -> cyt)
    'k_out': 1.2, #concentration based outward leak (cyt -> extra)

    #PMCA pump (Ca2+ Cyt -> Ca2+ Extracellular)
    'v_pmca': 10, #max PMCA pump flux
    'k_pmca': 2.5, #half-saturation of Ca2+ for PMCA

    #SOC channel (Ca2+ Extracellular -> Ca2+ Cyt)
    'v_soc': 1.57, #max SOC channel flux
    'k_soc': 90, #half-saturation of Ca2+ for SOC


    #Ratio of ER to Extracellular (Internal vs External) transmission rates
    'delta': 0.2,


    #----------------
    #Input parameters
    #----------------
    #These parmeters are used for different shapes of input

    # ------------------------
    # Double exponential curve
    # ------------------------

    #Initiate these variables
    'A': 0,
    'd_rise': 0,
    'r_rise': 0,
    'd_decay': 0,
    'r_decay': 0,
    't_star': 0, #when to start the IP3 transient



    #--------------------------------------------
    #Step input, pulse input and oscillation input
    #--------------------------------------------
    'step_max_value': 1, #maximum value during the ip3 step input
    'step_time_scale': 1,


    #Square wave glutamate pulse parameters
    'input_start': 10,
    'input_duration': 50,
    'input_max': 0.3,
    'input_min': 0,

    #Oscillation parameters
    'num_oscillations': 10,
    'oscillation_on_duration': 50,
    'oscillation_off_duration': 150,


    #
    #------------------------------
    #IP3 Generation and Degradation
    #------------------------------
    #'''
    #Production parameters
    'v_beta': 0.2,
    'v_delta': 0.01,
    'k_delta': 1.5,
    'k_plcdelta': 0.1,

    #Degradation parameters
    # 'v_3k': 2,
    'v_3k': 0.1,
    'k_d': 0.7,
    'k_3': 1,
    # 'r_5p': 0.08,
    'r_5p': 0.118,

    #-----------
    #Initial conditions
    #-----------
    't_0': 0,
    'gpcr_0': [0, 0, 0], #starting conditions for glutamate GPCR receptor

    #calcium starts at steady state
    #'ca_0': [0.0949, 34.8645, 0.6731] #starting conditions for calcium transients
    'ca_0': [0.0951442, 34.841184, 0.673079], #slightly more precise based on our numerical solve
    'x_0': [0.0951442, 34.841184, 0.673079, 0.056767761], #initial steady state conditions for IP3/Ca2+

    #initial conditions for full IP3/Ca/GPCR system
    'all_init': [0.0951442, 34.841184, 0.673079, 0.056767761, 0, 0, 0],
    #: [c, c_tot, h, p, Gstar, Gd1, Gd2],

    #Final time
    't_f': 1000,
}

#initiate these variables into globals variables
for param in init_param_dict:
    globals()[param] = init_param_dict[param]


#-------
#IP3 double exponential values from Marsa's paper
#-------
compute_r_decay = lambda A, d_decay: -1 / d_decay * np.log(0.005 / A)
#This dict contains some preset IP3 curve parameters so we can easily set
#which curve we want later
ip3_curves = {
    #Single peak
    'SP': {
        'A': 0.2,
        'd_rise': 21,
        'r_rise': 0.002,
        'd_decay': 97,
        'r_decay': compute_r_decay(0.2, 97)
    },
    #Multi peak
    'MP': {
        'A': 0.2,
        'd_rise': 41,
        'r_rise': 0.15,
        'd_decay': 179,
        'r_decay': compute_r_decay(0.2, 97)
    },
    #Plateau
    'PL': {
        'A': 0.375,
        'd_rise': 36,
        'r_rise': 0.002,
        'd_decay': 120,
        'r_decay': compute_r_decay(0.375, 120)
    }
}



'''
#############################

ODE Functions

#############################
'''




'''
--------------------------
ODE equations
--------------------------
These functions are called by the numerical solver. Given a vector of values
x, they return the functions for xdot
'''

def all_ode_equations(t, x, glutamate_input_type='pulse', Gstar_input_type=False):
    '''
    This is the ODE for the full Glutamate/GPCR/IP3/Calcium system
    We will in effect call ip3_ca_ode_equations (with manual_ip3=False)
    as well as gpcr_ode_equations
    
    Please make sure manual_ip3 == False
    
    IP3/Ca:
    c = x[0]
    c_tot = x[1]
    h = x[2]
    p = x[3]
    
    GPCR:
    Gstar = x[4]
    Gd1 = x[5]
    Gd2 = x[6]
    '''
    xdot = np.zeros(len(x))
    
    #manual Gstar
    #make sure to change this after
    if(Gstar_input_type is not False): 
        Gstar = get_input_value(Gstar_input_type, t)
        x[4] = Gstar
    
    #Note here we are passing Gstar to ip3_ode_equations
    xdot[:4] = ip3_ca_ode_equations(t, x[:4], ip3_input_type=None,
                                    Gstar=x[4])
    xdot[4:] = gpcr_ode_equations(t, x[4:], glutamate_input_type)
    
    return xdot





def gpcr_ode_equations(t, x, glutamate_input_type='pulse'):
    '''
    ODE equations following the GPCR equations given earlier
    x[0] = Gstar
    x[1] = Gd1
    x[2] = Gd2
    This returns x_dot, which is an array of the right hand sides of 
    each of the ODE equations in the same order as above
    '''
    Gstar = x[0]
    Gd1 = x[1]
    Gd2 = x[2]
    G = 1 - Gstar - Gd1 - Gd2
    
    #query our glutamate function for what level glutamate is input
    glut = get_input_value(glutamate_input_type, t)
    
    x_dot = np.zeros(3)
    
    x_dot[0] = kp*glut*G - km*Gstar - kd1*Gstar
    x_dot[1] = kd1*Gstar - kr1*Gd1
    x_dot[2] = kd2*Gstar*G - kr2*Gd2
    
    return x_dot





def ip3_ca_ode_equations(t, x, ip3_input_type=None, Gstar=None):
    '''
    ODE equations detailing the calcium transient response to a
    given IP3 level
    Pass Gstar in if we are doing the full ODE system
    '''
    c = x[0] #Cytosolic Ca2+ concentration
    c_tot = x[1] #Total free Ca2+ concentration in cell
    h = x[2] #Deactivation parameter for IP3R
    p = 0 #IP3 concentration
    
    
    #We can choose to either use ODE for IP3 or manually input it
    #ODE
    if(ip3_input_type == None):
        p = x[3] #IP3 concentration
    
    #Explicit input
    else:
        p = get_input_value(ip3_input_type, t)
    
    #Compute ER Ca2+ concentration based on total Ca2+ and Cyt Ca2+
    c_er = (c_tot - c) * gamma
    
    #First compute some derivative values that will be needed
    #for h and IP3R dynamics
    m_inf = p / (p + d1)
    n_inf = c / (c + d5)
    Q2 = d2 * (p + d1) / (p + d3)
    h_inf = Q2 / (Q2 + c)
    tau_h = 1 / (a2 * (Q2 + c))
    
    #Compute the fluxes through each channel
    J_ip3r = v_ip3r * (m_inf**3) * (n_inf**3) * (h**3) * (c_er - c)
    J_serca = v_serca * (c**1.75) / (c**1.75 + k_serca**1.75)
    J_pmca = v_pmca * (c**2) / (c**2 + k_pmca**2)
    J_soc = v_soc * (k_soc**4) / (k_soc**4 + c_er**4)
#     J_soc = v_soc * (k_soc**2) / (k_soc**2 + c_er**2)
    
    #leak fluxes
    J_er_leak = v_er_leak * (c_er - c) #ER <-> Cyt leak
    J_ecs_add = v_in - k_out * c #Cyt <-> extracellular leak
    
    x_dot = np.zeros(len(x))
    
    x_dot[0] = J_ip3r + J_er_leak - J_serca + delta*(J_ecs_add - J_pmca + J_soc)
    x_dot[1] = delta*(J_ecs_add - J_pmca + J_soc)
    x_dot[2] = (h_inf - h) / tau_h
    x_dot[3] = ip3_ode_equation(t, x, Gstar)
    
    return x_dot
    
    



def ip3_ode_equation(t, x, Gstar=None):
    '''
    ODE equations for IP3 production and degradation
    This function will be called by ip3_ca_ode_equations if
    manual_ip3 is set to False and we are simulating dynamics
    '''
    c = x[0] #Cytosolic Ca2+ concentration
    c_tot = x[1] #Total free Ca2+ concentration in cell
    h = x[2] #Deactivation parameter for IP3R
    p = x[3] #IP3 concentration 
    
    if(Gstar == None):
        #use a square wave for Gstar for now
        Gstar = pulse_input(t)
        #Gstar = 0
        
    ip3_production = v_beta*Gstar + v_delta*((k_delta)/(1 + p))*((c**2)/(c**2 + k_plcdelta**2))
    ip3_degradation = v_3k*((c**4)/(c**4 + k_d**4))*(p/(p+k_3)) + r_5p*p
#     ip3_degradation = v_3k*((c**2)/(c**2 + k_d**2))*(p/(p+k_3)) + r_5p*p
    
    return ip3_production - ip3_degradation

    
    



'''
--------------------------
Input functions
--------------------------
These functions are used to give manual input for glutamate or IP3
The exact shape of input can be modified by changing global parameters
One of the following input string types should be passed in the 
    run_experiment functions

E.g., input_duration = 500
    will make a 'pulse' type input last for 500 seconds

Input types:
    'pulse': used for constant input value, params are
        input_start:        when the input starts
        input_duration:     how long input lasts
        input_max:          how large the input is when on
        input_min:          how large the input is when off
    'step': used for input that will step up every 150s uniformly to a max 
        step_max_value:     the max value the step will reach
        e.g. if it is 1, the steps will be [0, 0.25, 0.5, 0.75, 0.1, 0.75, 0.5, 0.25, 0]
        step_time_scale:    how long each step will last
        e.g. if it is 1, each step lasts 150s, if it is 2, each step lasts 300s
    'oscillation': input will oscillate between on and off
        input_min, input_max: min/max values of oscillation
        num_oscilations:      how many oscillations
        oscillation_on_duration, oscillation_off_duration: how long each on/off 
                                                           phase will last
    'exponential_oscillation': same as 'oscillation' but will rise and fall
        exponentially
    'curve': this is a double exponential curve
        A, d_rise, d_decay, r_rise, r_decay
'''

def get_input_value(input_type, t):
    '''
    Helper function - given a certain input type and time t
    return the value for the input
    '''
    if(input_type == 'pulse'):
        return pulse_input(t)
    elif(input_type == 'step'):
        return step_input(t)
    elif(input_type == 'oscillation'):
        return oscillation_input(t)
    elif(input_type == 'curve'):
        return curve_input(t)
    elif(input_type == 'exponential_oscillation'):
        return exponential_oscillation(t)

    else:
        return 0




def get_input_plot(input_type):
    '''
    This function simply returns t and y values to plot
    based on the type of input curve that we used
    E.g., we could call this to get glut_t, glut for the glutamate
    input plot
    '''
    t = np.arange(t_0, t_f, 0.1)
    y = []
    for x in t:
        y.append(get_input_value(input_type, x))
    y = np.array(y)
    return t, y





def pulse_input(t):
    '''
    This function tells us what value glutamate takes at a given time t
    Currently set to square wave
    '''
    if(t > input_start and t < (input_start + input_duration)):
        glut = input_max
    else:
        glut = input_min
    return glut





def oscillation_input(t):
    '''
    This function creates an oscillatory glutamate input
    '''
    principle_t = (t) % (oscillation_on_duration + oscillation_off_duration)
    
#     print((oscillation_off_duration + oscillation_on_duration) * num_oscillations)
    if(principle_t < oscillation_on_duration and
        t < (oscillation_off_duration + oscillation_on_duration) * num_oscillations):
        return input_max
    else:
        return input_min

    
    
    

def exponential_oscillation(t):
    '''
    This function creates an oscillatory glutamate input where the input grows
    and falls exponentially
    '''
    #compute our IP3 curve helper functions
    oscillation_on_duration = d_rise + d_decay
    principle_t = t % (oscillation_on_duration + oscillation_off_duration)
    
    if(principle_t < oscillation_on_duration and
      t < (oscillation_on_duration + oscillation_off_duration) * num_oscillations):
        s_inf = A / (1 - np.exp(-r_rise * d_rise))
        if(principle_t < d_rise):
            return s_inf * (1 - np.exp(-r_rise * (principle_t)))
        elif(principle_t >= d_rise):
            return A * np.exp(-r_decay * (principle_t - d_rise))
    else:
        return 0





def exponential_input(t):
    '''
    This function will generate an exponential increase and decay glutamate input
    '''
    input_half = input_duration / 2
    if(t > input_start and t <= (input_start + input_half)):
        return input_max * (1 - np.exp((t - input_start) / (t - input_start - input_half)))
    elif(t > (input_start + input_half) and t <= (input_start + input_duration)):
        return input_max * np.exp((t - input_start - input_half) / (t - input_start - input_duration))
    else:
        return input_min





def curve_input(t):
    '''
    This function tell us what value IP3 takes at a given time t
    if we want to expicitly use IP3 as an input to compute
    the calcium dynamics for a given IP3 transient
    To set the parameters for this curve, use set_ip3_curve()
    '''
    #compute our IP3 curve helper functions
    if(A != 0):
        s_inf = A / (1 - np.exp(-r_rise * d_rise))
        if(t < t_star):
            return 0
        elif(t >= t_star and t < (t_star + d_rise)):
            return s_inf * (1 - np.exp(-r_rise * (t - t_star)))
        elif(t >= (t_star + d_rise)):
            return A * np.exp(-r_decay * (t - t_star - d_rise))
    else:
        #return steady state IP3
        return 0.056767761
    
    



def step_input(t):
    '''
    This function will create an IP3 input that increases stepwise
    0-50s: 0
    50-200s: 0.125
    200-350s: 0.250
    350-500s: 0.375
    500-650s: 0.5
    650-800s: 0.375
    800-950s: 0.250
    950-1100s: 0.125
    1100s-: 0
    '''
    #times at which the concentration changes
    time_breaks = np.array([0, 50, 200, 350, 500, 650, 800, 950, 1100]) * step_time_scale
    #values the concentration changes to at each interval
    input_values = np.array([0, 0.25, 0.5, 0.75, 1, 0.75, 0.5, 0.25, 0]) * step_max_value

    for i in range(len(time_breaks)):
        #check if t is after last time_break
        if(i == len(time_breaks) - 1):
            if(t >= time_breaks[i]):
                return input_values[i]

        #check which interval t is in
        else:
            if(t >= time_breaks[i] and t < time_breaks[i+1]):
                return input_values[i]

    
    


def set_ip3_curve(curve, t=100):
    '''
    This function will set the parameters for our ip3 curve
    curve: the type of curve desired, options are
        'singlepeak'/'SP': IP3 curve that should produce SP
        'multipeak'/'MP': IP3 curve that should produce MP
        'plateau'/'PL': IP3 curve that should produce PL
        'steadystate'/'SS': IP3 set to flat 0.05676
        
    t_star: when to start the IP3 transient, default is 100ms
    '''
    global A
    global d_rise
    global d_decay
    global r_rise
    global r_decay
    global t_star

    t_star = t
    curves = ['singlepeak', 'SP', 'multipeak', 'MP', 'plateau', 'PL']
    
    if(curve in curves):
        if(curve == 'singlepeak'):
            curve = 'SP'
        elif(curve == 'multipeak'):
            curve = 'MP'
        elif(curve == 'plateau'):
            curve = 'PL'
        A = ip3_curves[curve]['A']
        d_rise = ip3_curves[curve]['d_rise']
        d_decay = ip3_curves[curve]['d_decay']
        r_rise = ip3_curves[curve]['r_rise']
        r_decay = ip3_curves[curve]['r_decay']
        
    elif(curve in ['steadystate', 'SS']):
        A = 0
    else:
        raise Exception('No proper IP3 curve option was selected, check documentation')
        




'''

############################

Experiment running functions

############################
These functions will each run an experiment with the given control parameter

!!NOTE: These functions should be manually copied to any notebook that calls
on the solution variables directly, since the variables will be saved to
the global values of the ip3_ca_ode module

run_ip3_controlled_experiment: Run ODE with the given IP3 input
run_Gstar_controlled_experiment: Run ODE with the given Gstar input
run_experiment: Run ODE with the given glutamate input

The results of the experiment will be saved to the global space e.g.
t: time value of each step of ODE solve
p, c, h, c_tot: value of variable at each step of ODE solve
t_input: time values used to plot the input parameter
    For example, if controlling IP3, we would plot
    plt.plot(t_input, p)
    to see what the IP3 input looked like
'''

def run_ip3_controlled_experiment(input_type, t_f=1000, max_step=0.1):
    '''
    Run an experiment where ip3 is manually given by the specified input type
    '''
    global t
    global p
    global c
    global c_tot
    global h
    global t_input
    
    sol = scipy.integrate.solve_ivp(ip3_ca_ode_equations, [t_0, t_f], x_0, 
                                    args=[input_type], max_step=max_step)
    sol['glutamate_input_type'] = input_type
    
    t = sol.t
    c = sol.y[0]
    c_tot = sol.y[1]
    h = sol.y[2]
    
    t_input, p = get_input_plot(input_type)
    return sol
    



def run_Gstar_controlled_experiment(input_type, t_f=1000, max_step=0.1):
    '''
    Run an experiment where Gstar is manunally given by the specified input type
    '''
    global t
    global p
    global c
    global c_tot
    global h
    global t_input
    global Gstar

    sol = scipy.integrate.solve_ivp(all_ode_equations, [t_0, t_f], all_init, 
                                    args=['pulse', input_type], max_step=max_step)
    sol['glutamate_input_type'] = input_type
    
    t = sol.t
    c = sol.y[0]
    c_tot = sol.y[1]
    h = sol.y[2]
    p = sol.y[3]
    
    
    t_input, Gstar = get_input_plot(input_type)
    return sol




def run_experiment(input_type='pulse', t_f=1000, max_step=0.1):
    '''
    Run an experiment where glutamate is manually given by the specified input type
    '''
    global t
    global p
    global c
    global c_tot
    global h
    global t_input
    global Gstar
    global glut
    
    sol = scipy.integrate.solve_ivp(all_ode_equations, [t_0, t_f], all_init, 
                                  args=[input_type], max_step=max_step)
    
    t = sol.t
    c = sol.y[0]
    c_tot = sol.y[1]
    h = sol.y[2]
    p = sol.y[3]
    Gstar = sol.y[4]
    t_input, glut = get_input_plot(input_type)
    
    
    return sol





'''
###########################

Plotting Functions

###########################
These functions help with quickly plotting results from the numerical solver
or from XPP saved data
'''

def plot_experiment_plots(variables, axs, add_ylabels=True, add_xlabel=True, plot_input=True, 
                          ylabel_padding=[-0.23, 0.4]):
    '''
    Plot the solutions of the numerical solver for multiple variables
    Use the passed axs, iterating through them one by one and plotting the variables in the given order
    
    variables: list of variable names e.g. ['Gstar', 'p', 'h', 'c']
    axs: list of axes to plot on. For example a column of plots from plt.subplots
    add_ylabels: whether to add ylabels to the plot
    add_xlabel: whether to add xlabel of time to the last axis
    plot_input: whether first plot is an input (then we will use t_input instead of t)
    ylabel_padding: padding for each ylabel (first is x direction, second is y direction)
    
    This should only be used if more than one variable is being plotted

    Ex.
    run_Gstar_controlled_experiment('pulse')
    fig, ax = plt.subplots(4, 1, figsize=(10, 5))
    plot_experiment_plots(['Gstar', 'p', 'h', 'c'], ax)
    '''
    ylabels = {
        'glut': r'$\phi$',
        'Gstar': r'$G^*$',
        'p': r'IP$_3$',
        'h': r'$h$',
        'c': r'$c$',
        'c_tot': r'$c_{tot}$'
    }
    
    for i, variable in enumerate(variables):
        y = globals()[variable]
        
        if(plot_input and i==0):
            axs[i].plot(t_input, y)
        else:
            axs[i].plot(t, y)
    
    if(add_ylabels):
        for i, variable in enumerate(variables):
            axs[i].set_ylabel(ylabels[variable], rotation='horizontal', ha='left')
            axs[i].get_yaxis().set_label_coords(ylabel_padding[0], ylabel_padding[1])
            
    if(add_xlabel):
        axs[len(variables) - 1].set_xlabel(r'$t$')
    



def plot_bifurcation(filename, ax=None, increasing=True, ret=False, jump_lim=0.01):
    '''
    Plot the bifurcation data based on XPPAUTO file (from AUTO > File > Write Points)    
    This will automatically look in the folder 'data/bifurcations/'

    ax: optionally pass in a matplotlib axis to plot on
    increasing: if True, only plot the x axis values that are increasing
        to avoid repeating plotting oscillatory bifurcation curves that tend to double
        back on themselves
    ret: if True, return the dataframe
    jump_lim: amount by which points must jump before considered a split. If things
        are joining weirdly, decrease this value. If things are not being plotted, 
        increase this value

    Ex.
    plot_bifurcation('ip3_ca.dat')
    '''
    if(type(ax) == type(None)):
        ax = plt
    data = load_bifurcation_data(filename)
    
    for i, bifurc_type in enumerate(colors.keys()):
        d = data[data[3] == i+1]
        splits = np.where(np.abs(d[0].diff()) > jump_lim)[0] #check where the plot splits up and plot 
                                                  #each individual portion of the data
        if(increasing):
            if(d[0].diff().sum() < 0):
                final_index = np.argmin(d[0])
            else:
                final_index = np.argmax(d[0]) #find where the x-axis value no longer increasing
            if(final_index == 0):
                final_index = len(d[0])
#             print(final_index)
            
        if(len(splits) == 0):
            if(increasing):
                end = final_index
            else:
                end = None

            ax.plot(d.iloc[:end, 0], d.iloc[:end, 1], c=colors[bifurc_type], linestyle=linestyles[bifurc_type])
            ax.plot(d.iloc[:end, 0], d.iloc[:end, 2], c=colors[bifurc_type], linestyle=linestyles[bifurc_type])
        else:
            #plot the branches of the bifurcation type
            for j in range(len(splits) + 1):
                if(j == 0):
                    start = 0 #first split starts at 0
                else:
                    start = splits[j - 1]

                if(j == len(splits)):
                    end = None #last split contains all remaining data points
                else:
                    end = splits[j]
                
                if(increasing and (end == None or end > final_index)):
                    end = final_index
                    
                ax.plot(d.iloc[start:end, 0], d.iloc[start:end, 1], c=colors[bifurc_type], linestyle=linestyles[bifurc_type])
                ax.plot(d.iloc[start:end, 0], d.iloc[start:end, 2], c=colors[bifurc_type], linestyle=linestyles[bifurc_type])
    if(ret):
        return data
    
    



def load_bifurcation_data(filename, folder='data/bifurcations/'):
    '''
    Helper function called by plot_bifurcation
    Load the bifurcation data file given by XPP Auto
    in the data/bifurcations folder with the given filename
    '''
    data = []
    with open(folder + filename, 'rb') as f:
        for line in f:
            line = line.split()
            data_dict = {}
            for i, n in enumerate(line):
                data_dict[i] = float(n)
            data.append(data_dict)

    data = pd.DataFrame(data)
    return data




def plot_nullcline(filename, ax=None, ret=False, plot=True):
    '''
    Plot the nullclines from an XPP file
    Will automatically look in the folder 'data/nullclines/' for .dat file

    ax: optional matplotlib axis to plot the nullclines on
    ret: (True/False) whether to return the nullcline data
        'anim': pass this to return the data in specific form to be animated
    plot: whether to actually plot the nullcline

    Note, we can run this with ret=True, plot=False to more easily get
    the nullcline data to work with manually

    '''
    if(type(ax) == type(None)):
        ax = plt
    data = load_nullcline(filename)
    
    if(plot):
        for nc_type in [1, 2]:
            indexes = data[data['type'] == nc_type].index

            if(nc_type == 1):
                color = 'red'
                label = 'p'
            elif(nc_type == 2):
                color = 'green'
                label = 'c'
            for i in indexes: 
                ax.plot([data.loc[i,'x1'], data.loc[i,'x2']], [data.loc[i,'y1'], data.loc[i,'y2']], c=color,
                        label=label)
                label = None
    
    
    if(ret is True):
        return data
    if(ret == 'anim'):
        plot_data = []
        for nc_type in [1, 2]:
            data_block = data[data['type'] == nc_type]
            plot_data.append([data_block['x1'], data_block['y1']])
        return plot_data




def load_nullcline(filename, folder='data/nullclines/'):
    '''
    Helper function called by plot_nullcline
    Gets the nullcline data from data/nullclines
    '''
    data = []
    with open(folder + filename, 'rb') as f:
        nc_type = 1
        even_odd = 0
        for line in f:
            if(line == b'# X-nullcline\n'):
                nc_type = 1
            elif(line == b'# Y-nullcline\n'):
                nc_type = 2
            else:
                line = line.split()
                if(len(line) > 0):
                    #this is a data line
                    if(even_odd == 0):
                        even_odd = 1
                        x1 = float(line[0])
                        y1 = float(line[1])
                    else:
                        even_odd = 0
                        x2 = float(line[0])
                        y2 = float(line[1])
                        data.append([x1, x2, y1, y2, nc_type])

    data = pd.DataFrame(data, columns=['x1', 'x2', 'y1', 'y2', 'type'])
    return data