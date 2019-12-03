import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.stats import norm
import pdb
import warnings
import SolveLinSys1
import SolveLinSys2
import time
import sys
from scipy.interpolate import CubicSpline
from scipy.interpolate import RegularGridInterpolator
from scipy.interpolate import RectBivariateSpline
import itertools
from collections import OrderedDict, Counter
from supportfunctions import *
from estimate_damages import *
import pickle
import os

from IPython.core.display import display, HTML
import plotly.io as pio
import matplotlib.pyplot as plt
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from plotly.offline import init_notebook_mode, iplot
from scipy.interpolate import CubicSpline

sys.stdout.flush()

# to-dos:
# 1. remove Ambiguity Netreal variable
# 2. test ploting module
# 3. combine growth codes
# 4. group legends

# Parameters for the model
defaultParams = OrderedDict({})
defaultParams['δ'] = 0.01  # subjective rate of discount
defaultParams['κ'] = 0.032      
defaultParams['σ𝘨'] = 0.02
defaultParams['σ𝘬'] = 0.0161
defaultParams['σ𝘳'] = 0.0339 
defaultParams['α'] = 0.115000000000000
defaultParams['ϕ0'] = 0.0600
defaultParams['ϕ1'] = 16.666666666666668
defaultParams['μ̄ₖ'] = -0.034977443912449
defaultParams['ψ0'] = 0.112733407891680
defaultParams['ψ1'] = 0.142857142857143
# parameters for damage function
defaultParams['power'] = 2 
defaultParams['γ1'] = 0.00017675
defaultParams['γ2'] = 2. * 0.0022
defaultParams['γ2_plus'] = 2. * 0.0197
defaultParams['σ1'] = 0
defaultParams['σ2'] = 0
defaultParams['ρ12'] = 0
defaultParams['F̄'] = 2
defaultParams['crit'] = 2
defaultParams['F0'] = 1
defaultParams['ξₚ'] = 1 / 0.001   # 4500, 0.01
McD = np.loadtxt('TCRE_MacDougallEtAl2017_update.txt')
defaultParams['βMcD'] = McD / 1000.0
# defaultParams['weight'] = 0.0

# Specification for Model's solver
solverSpecification = OrderedDict({})
solverSpecification['tol'] = 1e-10
solverSpecification['ε'] = 0.5
solverSpecification['R_min'] = 0
solverSpecification['R_max'] = 9
solverSpecification['nR'] = 30
solverSpecification['F_min'] = 0
solverSpecification['F_max'] = 4000
solverSpecification['nF'] = 40
solverSpecification['K_min'] = 0
solverSpecification['K_max'] = 9
solverSpecification['nK'] = 25
solverSpecification['quadrature'] = 'legendre'
solverSpecification['n'] = 30

# Specification for the model
modelType = OrderedDict({})
modelType['damageSpec'] = 'Preference'    # Preference or Growth
modelType['damageFunc'] = 'High'          # High, low or weight
modelType['AmbiguitySpec'] = 'Averse'     # Averse or Neutral


class GridInterp():

    def __init__(self, grids, values, method = 'Linear'):

        # unpacking
        self.grids = grids
        (self.xs, self.ys, self.zs) = grids
        self.nx = len(self.xs)
        self.ny = len(self.ys)
        self.nz = len(self.zs)
        
        self.values = values

        assert (self.nx, self.ny, self.nz) == values.shape, "ValueError: Dimensions not match"
        self.method = method

    def get_value(self, x, y, z):

        if self.method == 'Linear':
            
            func = RegularGridInterpolator(self.grids, self.values)
            return func([x,y,z])[0]

        elif self.method == 'Spline':

            func1 = CubicSpline(self.xs, self.values)
            yzSpace = func1(x)
            
            func2 = CubicSpline(self.ys, yzSpace)
            zSpace = func2(y)
            
            func3 = CubicSpline(self.zs, zSpace)
            return func3(z)

        else:
            raise ValueError('Method Not Supported')


class modelSolutions():

    def __init__(self, params = defaultParams, specs = solverSpecification, method = 'Linear'):
        self.modelParams = params
        self.solverSpecs = specs
        self.models = {}
        self.xiModels = {}
        # self.keys = ['HighAverse', 'HighNeutral', 'LowAverse', 'LowNeutral', 'WeightedAverse', 'WeightedNeutral']
        self.SCCNets = None
        self.method = method

    def solveProblem(self):

        if os.path.isfile('./HighAverse.pickle'):
            self.models['HighAverse'] = pickle.load(open("./HighAverse.pickle", "rb", -1))
        else:
            self.modelParams['ξₚ'] = 1 / 4500
            self.models['HighAverse'] = climateModel(self.modelParams, self.solverSpecs)
            self.models['HighAverse'].solveHJB('High')
            self.models['HighAverse'].Simulate(self.method)
            self.models['HighAverse'].SCCDecompose(AmbiguityNeutral = False, method = self.method)
            self.models['HighAverse'].computeProbs(damageSpec = 'High', method = self.method)

        if os.path.isfile('./HighNeutral.pickle'):
            self.models['HighNeutral'] = pickle.load(open("./HighNeutral.pickle", "rb", -1))
        else:
            self.modelParams['ξₚ'] = 1 / 0.001
            self.models['HighNeutral'] = climateModel(self.modelParams, self.solverSpecs)
            self.models['HighNeutral'].solveHJB('High')
            self.models['HighNeutral'].Simulate(self.method)
            self.models['HighNeutral'].SCCDecompose(AmbiguityNeutral = True, method = self.method)

        if os.path.isfile('./LowAverse.pickle'):
            self.models['LowAverse'] = pickle.load(open("./LowAverse.pickle", "rb", -1))
        else:
            self.modelParams['ξₚ'] = 1 / 4500
            self.models['LowAverse'] = climateModel(self.modelParams, self.solverSpecs)
            self.models['LowAverse'].solveHJB('Low')
            self.models['LowAverse'].Simulate(self.method)
            self.models['LowAverse'].SCCDecompose(AmbiguityNeutral = False, method = self.method)
            self.models['LowAverse'].computeProbs(damageSpec = 'Low', method = self.method)

        if os.path.isfile('./LowNeutral.pickle'):
            self.models['LowNeutral'] = pickle.load(open("./LowNeutral.pickle", "rb", -1))
        else:
            self.modelParams['ξₚ'] = 1 / 0.001
            self.models['LowNeutral'] = climateModel(self.modelParams, self.solverSpecs)
            self.models['LowNeutral'].solveHJB('Low')
            self.models['LowNeutral'].Simulate(self.method)
            self.models['LowNeutral'].SCCDecompose(AmbiguityNeutral = True, method = self.method)

        if os.path.isfile('./WeightedAverse.pickle'):
            self.models['WeightedAverse'] = pickle.load(open("./WeightedAverse.pickle", "rb", -1))
        else:
            self.modelParams['ξₚ'] = 1 / 4500
            self.models['WeightedAverse'] = climateModel(self.modelParams, self.solverSpecs)
            self.models['WeightedAverse'].solveHJB('Weighted')
            self.models['WeightedAverse'].Simulate(self.method)
            self.models['WeightedAverse'].SCCDecompose(AmbiguityNeutral = False, method = self.method)
            self.models['WeightedAverse'].computeProbs(damageSpec = 'Weighted', method = self.method)

        if os.path.isfile('./WeightedNeutral.pickle'):
            self.models['WeightedNeutral'] = pickle.load(open("./WeightedNeutral.pickle", "rb", -1))
        else:
            self.modelParams['ξₚ'] = 1 / 0.001
            self.models['WeightedNeutral'] = climateModel(self.modelParams, self.solverSpecs)
            self.models['WeightedNeutral'].solveHJB('Weighted')
            self.models['WeightedNeutral'].Simulate(self.method)
            self.models['WeightedNeutral'].SCCDecompose(AmbiguityNeutral = False, method = self.method)

    def solvexiModels(self, xiList = [ 1 / 4500, 0.0003, 0.0004, 0.0006, 0.001, 0.002, 0.005, 0.1, 1, 100, 1000], key = 'Weighted'):
        if os.path.isfile('./ximodels.pickle'):
            self.xiModels = pickle.load(open("./ximodels.pickle", "rb", -1))
            for ξ in xiList:
                if ξ == 1 / 0.001:
                    self.xiModels[ξ] = self.models['WeightedNeutral']
                elif ξ == 1 / 4500:
                    self.xiModels[ξ] = self.models['WeightedAverse']
                elif ξ in self.xiModels.keys():
                    pass
                else:
                    self.modelParams['ξₚ'] = ξ
                    self.xiModels[ξ] = climateModel(self.modelParams, self.solverSpecs)
                    self.xiModels[ξ].solveHJB(key)
                    self.xiModels[ξ].Simulate(method = self.method)
                    self.xiModels[ξ].SCCDecompose(AmbiguityNeutral = False, method = self.method)
        else:
            for ξ in xiList:
                if ξ == 1 / 0.001:

                    self.xiModels[ξ] = self.models['WeightedNeutral']

                elif ξ == 1 / 4500:

                    self.xiModels[ξ] = self.models['WeightedAverse']

                else:
                    self.modelParams['ξₚ'] = ξ
                    self.xiModels[ξ] = climateModel(self.modelParams, self.solverSpecs)
                    self.xiModels[ξ].solveHJB(key)
                    self.xiModels[ξ].Simulate(self.method)
                    self.xiModels[ξ].SCCDecompose(AmbiguityNeutral = False, method = self.method)

        xiList = sorted(self.xiModels.keys())
        for ξ in xiList:
            if self.SCCNets is None:

                self.SCCNets = self.xiModels[ξ].SCCs['SCC']

            else:
                self.SCCNets = np.vstack([self.SCCNets, self.xiModels[ξ].SCCs['SCC']])

                          # high/low/weighted                  Averse/Neutral


    def densityPlot(self, key = 'Weighted'):
        years = [50, 75, 100]

        titles = ["Year {}".format(year) for year in years]
            
        fig = make_subplots(1, len(years), print_grid = False, subplot_titles = titles)

        dom = self.models[key + 'Averse'].beta_f_space
        inds = ((dom>=0) & (dom<=5e-3))
        for i, year in enumerate(years):
            # data = loadmat("{}/50-50 weight/Dist_{}yr.mat".format(quad_rule, year))
            data = self.models[key+ 'Averse'].Dists
            if key == 'Weighted': 
                if i == 0:
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Original'][inds], row = 1, col = i + 1,
                        name = 'Original Distribution', line = dict(color = '#1f77b4', width = 3), showlegend = True, legendgroup = 'Original Distribution')
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Nordhaus_year' + str(year)][inds], row = 1, col = i + 1,
                        name = 'Low Damage Function', line = dict(color = 'red', dash='dashdot', width = 3), showlegend = True, legendgroup = 'Low Damage Function')
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Weitzman_year' + str(year)][inds], row = 1, col = i + 1,
                        name = 'High Damage Function', line = dict(color = 'green', dash='dash', width = 3), showlegend = True, legendgroup = 'High Damage Function')
                else:
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Original'][inds], row = 1, col = i + 1,
                        name = 'Original Distribution', line = dict(color = '#1f77b4', width = 3), showlegend = False, legendgroup = 'Original Distribution')
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Nordhaus_year' + str(year)][inds], row = 1, col = i + 1,
                        name = 'Low Damage Function', line = dict(color = 'red', dash='dashdot', width = 3), showlegend = False, legendgroup = 'Low Damage Function')
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Weitzman_year' + str(year)][inds], row = 1, col = i + 1,
                        name = 'High Damage Function', line = dict(color = 'green', dash='dash', width = 3), showlegend = False, legendgroup = 'High Damage Function')

            elif key == 'High':
                if i == 0:
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Original'][inds], row = 1, col = i + 1,
                        name = 'Original Distribution', line = dict(color = '#1f77b4', width = 3), showlegend = True, legendgroup = 'Original Distribution')
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Weitzman_year' + str(year)][inds], row = 1, col = i + 1,
                        name = 'High Damage Function', line = dict(color = 'green', dash='dash', width = 3), showlegend = True, legendgroup = 'High Damage Function')
                else:
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Original'][inds], row = 1, col = i + 1,
                        name = 'Original Distribution', line = dict(color = '#1f77b4', width = 3), showlegend = False, legendgroup = 'Original Distribution')
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Weitzman_year' + str(year)][inds], row = 1, col = i + 1,
                        name = 'High Damage Function', line = dict(color = 'green', dash='dash', width = 3), showlegend = False, legendgroup = 'High Damage Function')


            elif key == 'Low':
                if i == 0:
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Original'][inds], row = 1, col = i + 1,
                        name = 'Original Distribution', line = dict(color = '#1f77b4', width = 3), showlegend = True, legendgroup = 'Original Distribution')
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Nordhaus_year' + str(year)][inds], row = 1, col = i + 1,
                        name = 'Low Damage Function', line = dict(color = 'red', dash='dashdot', width = 3), showlegend = True, legendgroup = 'Low Damage Function')
                else:
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Original'][inds], row = 1, col = i + 1,
                        name = 'Original Distribution', line = dict(color = '#1f77b4', width = 3), showlegend = False, legendgroup = 'Original Distribution')
                    fig.add_scatter(x = dom[inds] * 1000, y = data['Nordhaus_year' + str(year)][inds], row = 1, col = i + 1,
                        name = 'Low Damage Function', line = dict(color = 'red', dash='dashdot', width = 3), showlegend = False, legendgroup = 'Low Damage Function')

        fig['layout'].update(title = key + " Damage Specification", showlegend = True, titlefont = dict(size = 20), height = 400)

        for i in range(len(years)):
            
            fig['layout']['yaxis{}'.format(i+1)].update(showgrid = False)
            fig['layout']['xaxis{}'.format(i+1)].update(showgrid = False)
            
        fig['layout']['yaxis1'].update(title=go.layout.yaxis.Title(
                                        text="Probability Density", font=dict(size=16)))
        fig['layout']['xaxis2'].update(title=go.layout.xaxis.Title(
                                        text="Climate Sensitivity", font=dict(size=16)), showgrid = False)

        fig = go.FigureWidget(fig)
        iplot(fig)

        # pio.write_image(fig, 'plots/Probability Densities for Climate Params {} Damage Case.pdf'.format(key), width=1500, height=600, scale=1)

    def SCCinterp(self, ξ):
        if ξ >= 0.01:
            xiList = sorted(self.xiModels.keys())
            func = RegularGridInterpolator((xiList, np.linspace(0,100,400)), self.SCCNets)
            # print('RegularGridInterpolator')
            return func(np.c_[ξ * np.ones(400), np.linspace(0,100,400)])
        else:
            xiList = sorted(self.xiModels.keys())
            func = RectBivariateSpline(xiList, np.linspace(0,100,400), self.SCCNets)
            return np.squeeze(func(ξ, np.linspace(0,100,400)))

    def SCCSmoothPlot(self):
        # colorscale=[ "rgb(165,0,38)",
        #          "rgb(215,48,39)",
        #          "rgb(244,109,67)",
        #          "rgb(253,174,97)",
        #          "rgb(255,160,122)",
        #          "rgb(254,224,144)",
        #          "rgb(224,243,248)",
        #          "rgb(171,217,233)",
        #          "rgb(116,173,209)",
        #          "rgb(69,117,180)",
        #          "rgb(49,54,149)"]

        if self.SCCNets is not None:
            fig = go.Figure()
            # line_data = []
            x = np.linspace(0,100,400)
            xiList = np.logspace(np.log10(1/4500), -2, 50)
            for ξ in xiList:
                fig.add_trace(go.Scatter(x = x, y = np.squeeze(self.SCCinterp(ξ)), visible = False,
                               name = 'ξ = {:.6f}'.format(ξ), line = dict(color = "rgb(253,174,97)", dash='dash', width = 2),\
                                       showlegend = True, legendgroup = 'Arbitrary ξ'))

            # print(np.squeeze(self.SCCinterp(ξ)).shape)
            fig.add_trace(go.Scatter(x = x, y = self.xiModels[1000].SCCs['SCC'], visible = True,
                       name = 'Ambiguity Neutral', line = dict(color = "rgb(49,54,149)", dash='solid', width = 2),\
                               showlegend = True))

            fig.add_trace(go.Scatter(x = x, y = self.xiModels[1 / 4500].SCCs['SCC'], visible = True,
                           name = 'Ambiguity Averse'.format(ξ), line = dict(color = "rgb(165,0,38)", dash='solid', width = 2),\
                                   showlegend = True))

            fig.data[10].visible = True

            steps = []
            for i in range(50):
                step = dict(
                    method = 'restyle',
                    args = ['visible', [False] * len(fig.data)],
                    label = 'ξ = ' + "{:.4f}".format(xiList[i])
                    )
                step['args'][1][i] = True
                step['args'][1][-1] = True
                step['args'][1][-2] = True
                # print(step['args'][1])

                steps.append(step)

            sliders = [dict(active = 10,
                currentvalue = {"prefix": "ξ： "},
                pad = {"t": 50},
                steps = steps)]


            # print(line_data)
            fig.update_layout(title = 'Social Cost of Carbon Comparison',
                      titlefont = dict(size = 20),
                      xaxis = go.layout.XAxis(title=go.layout.xaxis.Title(
                                        text='Years', font=dict(size=16)),
                                             tickfont=dict(size=12), showgrid = False),
                      yaxis = go.layout.YAxis(title=go.layout.yaxis.Title(
                                        text='Dollars per Ton of Carbon', font=dict(size=16)),
                                             tickfont=dict(size=12), showgrid = False),
                      sliders = sliders
                      )



            fig.show()
            # fig = dict(data = line_data, layout = layout)
            # iplot(fig)


        else:
            print('Models for different ξ was not initiated yet.')

    def SCCPlot(self, damageSpecs = ['High','Low','Weighted'], aversionSpecs = ['Averse'], key = 'CrossModel'):
        if key == 'CrossModel':

            colors = {'High': 'red', 'Low': 'green', 'Weighted': '#1f77b4'}
            lines = {'Averse': 'solid', "Neutral": 'dashdot'}

            line_data = []

            for i, ds in enumerate(damageSpecs):
                for j, avs in enumerate(aversionSpecs):
                    data = self.models[ds + avs].SCCs

                    total_SCC = np.array(data['SCC'])
                    
                    x = np.linspace(0,100,400)

                    line_data.append(go.Scatter(x = x, y = total_SCC,
                                   name = ds + ' Damage w/ Ambiguity ' + avs, line = dict(color = colors[ds], dash=lines[avs], width = 2),\
                                       showlegend = True))  
                
            # annotations=[dict(x=80, text="Weighted", textangle=0, ax=-100,
            #         ay=-75, font=dict(color="black", size=12), arrowcolor="black",
            #         arrowsize=3, arrowwidth=1, arrowhead=1),

            #         dict(x=80, y=302, text="Low Damage", textangle=0, ax=100,
            #         ay=50, font=dict(color="black", size=12), arrowcolor="black",
            #         arrowsize=3, arrowwidth=1, arrowhead=1),
                        
            #         dict(x=85, y=720, text="High Damage", textangle=0, ax=-100,
            #         ay=-75, font=dict(color="black", size=12), arrowcolor="black",
            #         arrowsize=3, arrowwidth=1, arrowhead=1)]

            layout = dict(title = 'Social Cost of Carbon Comparison',
                          titlefont = dict(size = 24),
                          xaxis = go.layout.XAxis(title=go.layout.xaxis.Title(
                                            text='Years', font=dict(size=16)),
                                                 tickfont=dict(size=12), showgrid = False),
                          yaxis = go.layout.YAxis(title=go.layout.yaxis.Title(
                                            text='Dollars per Ton of Carbon', font=dict(size=16)),
                                                 tickfont=dict(size=12), showgrid = False),
                          # annotations = annotations
                          legend = dict(orientation = 'h', y = 1.1)
                          )

                
            fig = go.Figure(data = line_data, layout = layout)
            figw = go.FigureWidget(fig)
            display(figw)

        elif key == 'CrossAmbiguityAversion':

            if len(self.xiModels) == 0:
                line_data = []
                
                x = np.linspace(0,100,400)

                line_data.append(go.Scatter(x = x, y = self.models['WeightedAverse'].SCCs['SCC'],
                           name = 'Ambiguity Averse', line = dict(color = '#1f77b4', dash='solid', width = 4),\
                                   showlegend = False))

                line_data.append(go.Scatter(x = x, 
                                        y = self.models['WeightedNeutral'].SCCs['SCC'], 
                                        name = "Ambiguity Neutral", 
                                        line = dict(color = "red", dash='dash', width = 4),
                                        showlegend = False))

                annotations=[dict(x=80, y=580, text="Ambiguity Averse", textangle=0, ax=-100,
                    ay=-75, font=dict(color="black", size=12), arrowcolor="black",
                    arrowsize=3, arrowwidth=1, arrowhead=1),

                    dict(x=80, y=420, text="Ambiguity Neutral", textangle=0, ax=100,
                    ay=75, font=dict(color="black", size=12), arrowcolor="black",
                    arrowsize=3, arrowwidth=1, arrowhead=1)]

                layout = dict(title = 'Social Cost of Carbon Comparison',
                          titlefont = dict(size = 24),
                          xaxis = go.layout.XAxis(title=go.layout.xaxis.Title(
                                            text='Years', font=dict(size=16)),
                                                 tickfont=dict(size=12), showgrid = False, showline = False),
                          yaxis = go.layout.YAxis(title=go.layout.yaxis.Title(
                                            text='Dollars per Ton of Carbon', font=dict(size=16)),
                                                 tickfont=dict(size=12), showgrid = False),
                          annotations = annotations
                          )


                fig = dict(data = line_data, layout = layout)
                iplot(fig)

            else:
                xiList = [ 1 / 4500, 0.0003, 0.0004, 0.0006, 0.001, 0.002, 0.005, 1, 100, 1000]
                colorscale=[ "rgb(165,0,38)",
                 # "rgb(190,20,38)",
                 "rgb(215,48,39)",
                 "rgb(244,109,67)",
                 "rgb(253,174,97)",
                 # "rgb(255,160,122)",
                 "rgb(254,224,144)",
                 # "rgb(224,243,248)",
                 "rgb(171,217,233)",
                 "rgb(130,180,210)",
                 "rgb(90,140,195)",
                 # "rgb(116,173,209)",
                 "rgb(69,117,180)",
                 "rgb(49,54,149)"]

                line_data = []

                x = np.linspace(0,100,400)
                for i, ξ in enumerate(xiList):
                    if i == len(xiList) - 1:
                        line_data.append(go.Scatter(x = x, y = self.xiModels[ξ].SCCs['SCC'],
                           name = 'Ambiguity Neutral', line = dict(color = colorscale[i], dash='solid', width = 2),\
                                   showlegend = True))

                    elif i == 0 :
                        line_data.append(go.Scatter(x = x, y = self.xiModels[ξ].SCCs['SCC'],
                               name = 'ξ = {:.4f}'.format(ξ), line = dict(color = colorscale[i], dash='solid', width = 2),\
                                       showlegend = True))
                    else:
                        line_data.append(go.Scatter(x = x, y = self.xiModels[ξ].SCCs['SCC'],
                               name = 'ξ = {:.4f}'.format(ξ), line = dict(color = colorscale[i], dash='dashdot', width = 2),\
                                       showlegend = True))
                # print(line_data)
                layout = dict(title = 'Social Cost of Carbon Comparison',
                          titlefont = dict(size = 20),
                          xaxis = go.layout.XAxis(title=go.layout.xaxis.Title(
                                            text='Years', font=dict(size=16)),
                                                 tickfont=dict(size=12), showgrid = False),
                          yaxis = go.layout.YAxis(title=go.layout.yaxis.Title(
                                            text='Dollars per Ton of Carbon', font=dict(size=16)),
                                                 tickfont=dict(size=12), showgrid = False)
                          )


                fig = dict(data = line_data, layout = layout)
                iplot(fig)


    def SCCDecomposePlot(self, key = 'Weighted'):

        if key == 'Low':

            data = self.models['LowAverse'].SCCs
            x1, y1, x2, y2, x3, y3 = 60, 195, 93, 330, 96, 100

        elif key == 'Weighted':

            data = self.models['WeightedAverse'].SCCs
            x1, y1, x2, y2, x3, y3 = 60, 320, 80, 315, 90, 350

        elif key == 'High':

            data = self.models['HighAverse'].SCCs
            x1, y1, x2, y2, x3, y3 = 60, 340, 93, 495, 96, 430


        total_SCC = np.array(data['SCC'])
        external_SCC = np.array(data['SCC2'])
        uncertainty_SCC = np.array(data['SCC3'])
        private_SCC = np.array(data['SCC1'])
        x = np.linspace(0,100,400)

        total = go.Scatter(x = x, y = total_SCC,
                       name = 'Total', line = dict(color = '#1f77b4', dash = 'solid', width = 3),\
                           showlegend = False)
        external = go.Scatter(x = x, y = external_SCC,
                       name = 'Ambiguity', line = dict(color = 'red', dash = 'dot', width = 3),\
                              showlegend = False)
        uncertainty = go.Scatter(x = x, y = uncertainty_SCC,
                       name = 'No Ambiguity', line = dict(color = 'green', dash = 'dashdot', width = 3),\
                                 showlegend = False)
        private = go.Scatter(x = x, y = private_SCC,
                       name = 'Private', line = dict(color = 'black', width = 3),\
                             showlegend = False)

        annotations=[dict(x=x1, y=y1, text="Total", textangle=0, ax=-100,
                    ay=-75, font=dict(color="black", size=12), arrowcolor="black",
                    arrowsize=3, arrowwidth=1, arrowhead=1),
                     
                    dict(x=x2, y=y2, text="Ambiguity", textangle=0, ax=-100,
                    ay=0, font=dict(color="black", size=12), arrowcolor="black",
                    arrowsize=3, arrowwidth=1, arrowhead=1),
                     
                    dict(x=x3, y=y3, text="No Ambiguity", textangle=0, ax=-80,
                    ay=80, font=dict(color="black", size=12), arrowcolor="black",
                    arrowsize=3, arrowwidth=1, arrowhead=1)]

        layout = dict(title = 'Social Cost of Carbon, {} Damage Specification'.format(key),
                      titlefont = dict(size = 24),
                      xaxis = go.layout.XAxis(title=go.layout.xaxis.Title(
                                        text='Years', font=dict(size=16)),
                                             tickfont=dict(size=12), showgrid = False),
                      yaxis = go.layout.YAxis(title=go.layout.yaxis.Title(
                                        text='Dollars per Ton of Carbon', font=dict(size=16)),
                                             tickfont=dict(size=12), showgrid = False), 
                      annotations=annotations
                      )

        fig = dict(data = [total, external, uncertainty], layout = layout)
        iplot(fig)

        fig['layout'].update(title = None)

    def emissionPlot(self, damageSpecs = ['High','Low','Weighted'], aversionSpecs = ['Averse']):

        colors = {'High': 'red', 'Low': 'green', 'Weighted': '#1f77b4'}
        lines = {'Averse': 'solid', "Neutral": 'dashdot'}

        # damageSpecs = ['High', 'Low', 'Weighted']
        # aversionSpecs = ['Averse', 'Neutral']
        # colors = ['green', '#1f77b4', 'red']
        # lines = ['solid', 'dashdot'] 

        x = np.linspace(0, 100, 400)
        data = []

        for ds in damageSpecs:
            for avs in aversionSpecs:
                data.append(go.Scatter(x = x, y = self.models[ds + avs].e_hists[:,0], name = ds + ' Damage w/ Ambiguity ' + avs,
                    line = dict(width = 2, dash = lines[avs], color = colors[ds]), showlegend = True))

        layout = dict(title = 'Emissions Comparison',
          titlefont = dict(size = 24),
          xaxis = go.layout.XAxis(title=go.layout.xaxis.Title(
                            text='Years', font=dict(size=16)),
                                 tickfont=dict(size=12), showgrid = False, showline = True),
          yaxis = go.layout.YAxis(title=go.layout.yaxis.Title(
                            text='Gigatons of Carbon', font=dict(size=16)),
                                 tickfont=dict(size=12), showgrid = False),
          legend = dict(orientation = 'h', y = 1.15)
          )

        fig = go.Figure(data = data, layout = layout)
        figw = go.FigureWidget(fig)
        display(figw)

    def preliminaryPlots(self):

        colors = {'High': 'red', 'Low': 'green', 'Weighted': '#1f77b4'}
        subplots = make_subplots(rows = 3, cols = 1, 
                    subplot_titles = ['Economic Damage Uncertainty',
                                      'Proportional Damage Uncertainty',
                                      'Macroeconomic Growth Rate Damages'])
        fig = go.FigureWidget(subplots)

        # Economic Damage Uncertainity
        x = np.arange(0, 5 + 0.01, 0.01)
        y_w = (1 / (1 + (x / 20.46) **2 + (x / 6.081) ** 6.754))
        y_n = (1 / (1 + 0.00227 * x ** 2))
        yhat_w, yhat_n, Tbar, coeffs = piecewise_est(x, y_w, y_n, 2)

        fig.add_trace(go.Scatter(x = x, y = yhat_n, name = 'Low Damages',
                                line = dict(width = 3), showlegend = False), row = 1, col = 1)
        fig.add_trace(go.Scatter(x = x, y = yhat_w, name = "High Damages", 
                     line = dict(width = 3, dash='dash', color = 'red'), showlegend = False), row = 1, col = 1)

        fig.update_xaxes(title_text = 'Temperature Increment over Pre-Industrial Levels (˚C)', row = 1 , col = 1)
        fig.update_yaxes(title_text = 'Proportional Reduction in Economic Welfare', range = [0.8,1.01], row = 1, col = 1)
        fig['layout'].update(shapes = [go.layout.Shape(type = 'line', xref = 'x1', yref = 'y1', x0 = 2, x1 = 2, y0 = 0, y1 = 1)])

        # Proportional Damage Uncertainty
        x = np.arange(0, 2.51, 0.01)
        def line_nordhaus(beta):
            return coeffs[0] * x * beta + coeffs[1] * (x * beta)**2

        def line_weitzman(beta):
            return coeffs[0] * x * beta + coeffs[1] * (x * beta)**2 + coeffs[2] * (x * beta - 2)**2 * (x * beta > 2)

        σ, μ = gen_distributions(0.0001)

        Int_nordhaus = quad_int(line_nordhaus, σ, μ, 150, 'hermite')
        Int_weitzman = quad_int(line_weitzman, σ, μ, 150, 'hermite')

        fig.add_trace(go.Scatter(x = x, y = np.exp(Int_nordhaus), name = 'Low Damage', line = dict(width = 3, color = colors['Low']), showlegend = False), row = 2, col = 1)
        fig.add_trace(go.Scatter(x = x, y = np.exp(0.5 * Int_nordhaus + 0.5 * Int_weitzman), name = 'Weighted', line = dict(width = 3, dash = 'dashdot', color = colors['Weighted']), showlegend = False), row = 2, col = 1)
        fig.add_trace(go.Scatter(x = x, y = np.exp(Int_weitzman), name = 'High Damage', line = dict(width = 3, dash = 'dash', color = colors['High']), showlegend = False), row = 2, col = 1)

        fig.update_xaxes(title_text = 'F: Cumulative Emissions', row = 2, col = 1)
        fig.update_yaxes(title_text = 'Proportional Reduction in Economic Welfare', row = 2, col = 1)

        # Macro Growth-Rate Damages
        x = np.arange(0, 5.01, 0.1)
        dec2, dec4, dec6, dec8 = Burke_bootstrap(x, 100000)

        fig.add_trace(go.Scatter(x = x, y = dec8, name = '80th Decile', line = dict(width = 3, color = "rgb(49,54,149)"), showlegend = False), row = 3, col = 1)
        fig.add_trace(go.Scatter(x = x, y = dec6, name = '60th Decile', line = dict(width = 3, color = "rgb(116,173,209)"), showlegend = False), row = 3, col = 1)
        fig.add_trace(go.Scatter(x = x, y = dec4, name = '40th Decile', line = dict(width = 3, color = "rgb(244,109,67)"), showlegend = False), row = 3, col = 1)
        fig.add_trace(go.Scatter(x = x, y = dec2, name = '20th Decile', line = dict(width = 3, color = "rgb(165,0,38)"), showlegend = False), row = 3, col = 1)

        fig.update_xaxes(title_text = 'Temperature Increment over Pre-Industrial Levels (˚C)', row = 3, col = 1)
        fig.update_yaxes(title_text = 'Growth Rate Impact', row = 3, col = 1)

        fig['layout']['annotations'] += tuple(
            [
            dict(
                x = 3.6, y = .92, text = 'High Damage', textangle = 0, ax = -100, ay = 75, showarrow = True,  font = dict(color = 'black', size = 12), arrowsize = 2, arrowwidth = 1, arrowhead = 1, xref = 'x1', yref = 'y1'
                ),
            dict(
                x = 4, y = .96, text = 'Low Damage', textangle = 0, ax = 75, ay = 25, showarrow = True, font = dict(color = 'black', size = 12), arrowsize = 2, arrowwidth = 1, arrowhead = 1, xref = 'x1', yref = 'y1'
                ),
            dict(
                x = 1.98, y = .85, text = 'Carbon Budget', textangle = 0, ax = -100, ay = 0, showarrow = True, font = dict(color = 'black', size = 12), arrowsize = 2, arrowwidth = 1, arrowhead = 1, xref = 'x1', yref = 'y1'
                ),
            dict(
                x = 1.5, y = .958, text = 'High Damage', textangle = 0, ax = -100, ay = 75, showarrow = True, font = dict(color = 'black', size = 12), arrowsize = 2, arrowwidth = 1, arrowhead = 1, xref = 'x2', yref = 'y2'
                ),
            dict(
                x = 1.8, y = .953, text = 'Weighted', textangle = 0, ax = -100, ay = 75, showarrow = True, font = dict(color = 'black', size = 12), arrowsize = 2, arrowwidth = 1, arrowhead = 1, xref = 'x2', yref = 'y2'
                ),
            dict(
                x = 2, y = .973, text = 'Low Damage', textangle = 0, ax = 80, ay = -20, showarrow = True, font = dict(color = 'black', size = 12), arrowsize = 2, arrowwidth = 1, arrowhead = 1, xref = 'x2', yref = 'y2'
                )
            ]
            )

        fig.update_layout(height=1000, title_text='Damage Specifications', titlefont = dict(size = 20))


        fig.show()
    

      
class climateModel():

    def __init__(self, params = defaultParams, specs = solverSpecification):

        self.modelParams = {}
        self.modelParams['δ'] = params['δ']
        self.modelParams['κ'] = params['κ']
        self.modelParams['σ𝘨'] = params['σ𝘨']
        self.modelParams['σ𝘬'] = params['σ𝘬']
        self.modelParams['σ𝘳'] = params['σ𝘳'] 
        self.modelParams['α'] = params['α']
        self.modelParams['ϕ0'] = params['ϕ0']
        self.modelParams['ϕ1'] = params['ϕ1']
        self.modelParams['μ̄ₖ'] = params['μ̄ₖ']
        self.modelParams['ψ0'] = params['ψ0']
        self.modelParams['ψ1'] = params['ψ1']
        # parameters for damage function
        self.modelParams['power'] = params['power']
        self.modelParams['γ1'] = params['γ1']
        self.modelParams['γ2'] = params['γ2']
        self.modelParams['γ2_plus'] = params['γ2_plus']
        self.modelParams['σ1'] = params['σ1']
        self.modelParams['σ2'] = params['σ2']
        self.modelParams['ρ12'] = params['ρ12']
        self.modelParams['F̄'] = params['F̄']
        self.modelParams['crit'] = params['crit']
        self.modelParams['F0'] = params['F0']
        self.modelParams['ξₚ'] = params['ξₚ']
        β𝘧 = np.mean(params['βMcD'])
        self.modelParams['β𝘧'] = β𝘧
        σᵦ = np.var(params['βMcD'], ddof = 1)
        self.modelParams['σᵦ'] = σᵦ
        self.modelParams['λ'] = 1.0 / σᵦ

        σ = np.matrix([[params['σ1'] ** 2, params['ρ12']], 
                        [params['ρ12'], params['σ2'] ** 2]])
        Σ = np.matrix([[σᵦ, 0, 0], 
                       [0, params['σ1'] ** 2, params['ρ12']], 
                       [0, params['ρ12'], params['σ2'] ** 2]])
        dee = np.matrix(
            [params['γ1'] + params['γ2'] * params['F0'] + params['γ2_plus']\
             * (params['F0'] - params['F̄']) ** 2 * (params['F0'] >= 2), 
            β𝘧, β𝘧 * params['F0']])

        self.modelParams['σ𝘥'] = float(np.sqrt(dee * Σ * dee.T))
        self.modelParams['xi_d'] = -1 * (1 - self.modelParams['κ'])
        # self.modelParams['γ̄2_plus'] = self.modelParams['weight'] * 0 + (1 - self.modelParams['weight']) * self.modelParams['γ2_plus']
        
        self._create_grid(specs)
        self.weight = None
        self.γ̄2_plus = None  # This is gammabar_2_plus, not the same as previous gamma2_plus

        self.v0 = self.modelParams['κ'] * self.R_mat + (1-self.modelParams['κ']) * self.K_mat - β𝘧 * self.F_mat

        self._initiate_interim_vars()

        # Specifying model types and solver arguments
        self.damageSpec = None
        self.quadrature = specs['quadrature']
        self.tol = specs['tol']
        self.ε = specs['ε']
        self.n = specs['n']
        self.status = 0
        self.stateSpace = np.hstack([self.R_mat.reshape(-1,1,order = 'F'),
            self.F_mat.reshape(-1,1,order = 'F'), self.K_mat.reshape(-1,1,order = 'F')])

    def _create_grid(self, specs):

        self.R = np.linspace(specs['R_min'],specs['R_max'], specs['nR'])
        self.F = np.linspace(specs['F_min'],specs['F_max'], specs['nF'])
        self.K = np.linspace(specs['K_min'],specs['K_max'], specs['nK'])

        self.hR = self.R[1] - self.R[0]
        self.hF = self.F[1] - self.F[0]
        self.hK = self.K[1] - self.K[0]

        (self.R_mat, self.F_mat, self.K_mat) = np.meshgrid(self.R, self.F, self.K, indexing = 'ij')
        
    def _initiate_interim_vars(self):

        self.e = np.zeros(self.R_mat.shape)
        self.i = np.zeros(self.R_mat.shape)
        self.j = np.zeros(self.R_mat.shape)
        self.v0 = np.zeros(self.R_mat.shape)
        self.π̃1 = np.zeros(self.R_mat.shape)
        self.π̃2 = np.zeros(self.R_mat.shape)
        self.β̃1 = np.zeros(self.R_mat.shape)
        self.λ̃1 = np.zeros(self.R_mat.shape)
        self.R1 = np.zeros(self.R_mat.shape)
        self.R2 = np.zeros(self.R_mat.shape)
        self.RE = np.zeros(self.R_mat.shape)
        self.beta_f_space = None
        self.hists = None
        self.i_hists = None
        self.j_hists = None
        self.e_hists = None
        self.v0_base = None
        self.v0_worst = None
        self.expec_e_sum = None
        self.SCCs = {}
        self.Dists = {}
        self.REs = {}
        self.fordebug = None
        

    def __PDESolver__(self, A, B_r, B_f, B_k, C_rr, C_ff, C_kk, D, solverType):

        if solverType == 'False Trasient':

            A = A.reshape(-1,1,order = 'F')
            B = np.hstack([B_r.reshape(-1,1,order = 'F'),B_f.reshape(-1,1,order = 'F'),B_k.reshape(-1,1,order = 'F')])
            C = np.hstack([C_rr.reshape(-1,1,order = 'F'), C_ff.reshape(-1,1,order = 'F'), C_kk.reshape(-1,1,order = 'F')])
            D = D.reshape(-1,1,order = 'F')
            v0 = self.v0.reshape(-1,1,order = 'F')
            # v1 = v0
            out = SolveLinSys1.solvels(self.stateSpace, A, B, C, D, v0, self.ε)
            # print(np.max(abs(v1 - v0)))
            return out

        elif solverType == 'Feyman Kac':
            A = A.reshape(-1, 1, order='F')
            B = np.hstack([B_r.reshape(-1, 1, order='F'), B_f.reshape(-1, 1, order='F'), B_k.reshape(-1, 1, order='F')])
            C = np.hstack([C_rr.reshape(-1, 1, order='F'), C_ff.reshape(-1, 1, order='F'), C_kk.reshape(-1, 1, order='F')])
            D = D.reshape(-1, 1, order='F')
            v0 = self.v0.reshape(-1, 1, order='F') * 0
            ε = 1.0
            out = SolveLinSys2.solvels(self.stateSpace, A, B, C, D, v0, ε)
            return out

        else:
            raise VauleError('Solver Type Not Supported')
            return None

    def solveHJB(self, damageSpec):
        # damageSpec ~ dictionary type that documents the 
        start_time = time.time()

        if damageSpec == 'High':
            self.weight = 0.0
        elif damageSpec == 'Low':
            self.weight = 1.0
        else:
            self.weight = 0.5

        # alter γ̄2_plus damage function additive term according to the model weight
        self.γ̄2_plus = self.weight * 0 + (1 - self.weight) * self.modelParams['γ2_plus']

        # unpacking the variables from model class
        δ  = self.modelParams['δ']
        κ  = self.modelParams['κ']
        σ𝘨 = self.modelParams['σ𝘨']
        σ𝘬 = self.modelParams['σ𝘬']
        σ𝘳 = self.modelParams['σ𝘳']
        α  = self.modelParams['α']
        ϕ0 = self.modelParams['ϕ0']
        ϕ1 = self.modelParams['ϕ1']
        μ̄ₖ = self.modelParams['μ̄ₖ'] 
        ψ0 = self.modelParams['ψ0']
        ψ1 = self.modelParams['ψ1']
        power = self.modelParams['power']
        γ1 = self.modelParams['γ1']
        γ2 = self.modelParams['γ2']
        γ2_plus = self.modelParams['γ2_plus']
        σ1 = self.modelParams['σ1']
        σ2 = self.modelParams['σ2']
        ρ12 = self.modelParams['ρ12'] 
        F̄ = self.modelParams['F̄']
        crit = self.modelParams['crit']
        F0 = self.modelParams['F0']
        ξₚ = self.modelParams['ξₚ']
        β𝘧 = self.modelParams['β𝘧']
        σᵦ = self.modelParams['σᵦ']
        λ = self.modelParams['λ']
        σ𝘥 = self.modelParams['σ𝘥']
        xi_d = self.modelParams['xi_d']
        γ̄2_plus = self.γ̄2_plus
        hR = self.hR
        hK = self.hK
        hF = self.hF
        n = self.n
        quadrature = self.quadrature


        R_mat = self.R_mat
        F_mat = self.F_mat
        K_mat = self.K_mat

        a = β𝘧 - 5 * np.sqrt(σᵦ)
        b = β𝘧 + 5 * np.sqrt(σᵦ)

        self.v0 = κ * R_mat + (1-κ) * K_mat - β𝘧 * F_mat
        v1_initial = self.v0 * np.ones(R_mat.shape)
        episode = 0

        while self.status == 0 or np.max(abs(out_comp - vold) / self.ε) > self.tol:

            vold = self.v0.copy()
            # Applying finite difference scheme to the value function
            v0_dr = finiteDiff(self.v0,0,1,hR,1e-8) 
            v0_df = finiteDiff(self.v0,1,1,hF)
            v0_dk = finiteDiff(self.v0,2,1,hK)

            v0_drr = finiteDiff(self.v0,0,2,hR)
            v0_dff = finiteDiff(self.v0,1,2,hF)
            v0_dkk = finiteDiff(self.v0,2,2,hK)

            if self.status == 0:
                # First time into the loop
                B1 = v0_dr - xi_d * (γ1 + γ2 * F_mat * β𝘧 + γ2_plus * (F_mat * β𝘧 - F̄) ** (power - 1) * (F_mat >= (crit / β𝘧))) * β𝘧 * np.exp(R_mat) - v0_df * np.exp(R_mat)
                C1 = - δ * κ
                self.e = -C1 / B1
                e_hat = self.e
                Acoeff = np.exp(R_mat - K_mat)
                Bcoeff = δ * (1-κ) / (np.exp(-R_mat + K_mat) * v0_dr * ψ0 * 0.5) + v0_dk * ϕ0 / (np.exp(-R_mat + K_mat) * v0_dr * ψ0 * 0.5)
                Ccoeff = -α  - 1 / ϕ1
                self.j = ((-Bcoeff + np.sqrt(Bcoeff ** 2 - 4 * Acoeff * Ccoeff)) / (2 * Acoeff)) ** 2
                self.i = (v0_dk * ϕ0 / (np.exp(-R_mat + K_mat) * v0_dr * ψ0 * 0.5)) * (self.j ** 0.5) - 1 / ϕ1
            else:
                e_hat = e_star
                self.j = ((α + 1 / ϕ1) * np.exp(-R_mat + K_mat) * (v0_dr * ψ0 * ψ1) / ((v0_dr * ψ0 * ψ1) * self.j ** (ψ1) + (δ * (1-κ) + v0_dk * ϕ0))) ** (1 / (1 - ψ1))
                self.j = self.j * (v0_dr > 1e-8)
                self.i = ((v0_dk * ϕ0 / (np.exp(-R_mat + K_mat) * v0_dr * ψ0 * ψ1)) * (self.j ** (1 - ψ1)) - 1 / ϕ1) * (v0_dr > 1e-8) + (v0_dr <= 1e-8) * (v0_dk * ϕ0 * α - δ * (1-κ) / ϕ1) / (δ * (1-κ) + v0_dk * ϕ0)
            
            self.a1 = np.zeros(R_mat.shape)
            b1 = xi_d * e_hat * np.exp(R_mat) * γ1
            c1 = 2 * xi_d * e_hat * np.exp(R_mat) * F_mat * γ2 
            self.λ̃1 = λ + c1 / ξₚ
            self.β̃1 = β𝘧 - c1 * β𝘧 / (ξₚ * self.λ̃1) -  b1 /  (ξₚ * self.λ̃1)
            I1 = self.a1 - 0.5 * np.log(λ) * ξₚ + 0.5 * np.log(self.λ̃1) * ξₚ + 0.5 * λ * β𝘧 ** 2 * ξₚ - 0.5 * self.λ̃1 * (self.β̃1) ** 2 * ξₚ
            #     R1 = \xi\_p.*(I1-(a1+b1.*β̃1+c1./2.*(β̃1).^2+c1./2./\lambda\tilde_1));
            self.R1 = 1 / ξₚ * (I1 - (self.a1 + b1 * self.β̃1 + c1 * self.β̃1 ** 2 + c1 / self.λ̃1))
            J1_without_e = xi_d * (γ1 * self.β̃1 + γ2 * F_mat * (self.β̃1 ** 2 + 1 / self.λ̃1)) * np.exp(R_mat)

            self.π̃1 = self.weight * np.exp(-1 / ξₚ * I1)

            def scale_2_fnc(x):
                return np.exp(-1 / ξₚ * xi_d * (γ1 * x + γ2 * x ** 2 * F_mat + γ2_plus * x * (x * F_mat - F̄) ** (power - 1) * ((x * F_mat - F̄) >= 0)) * np.exp(R_mat) * e_hat)  * norm.pdf(x,β𝘧,np.sqrt(σᵦ))
            
            scale_2 = quad_int(scale_2_fnc, a, b, n, 'legendre')

            def q2_tilde_fnc(x):
                return np.exp(-1 / ξₚ * xi_d * (γ1 * x + γ2 * x ** 2 * F_mat + γ2_plus * x * (x * F_mat - F̄) ** (power - 1) * ((x * F_mat - F̄) >= 0)) * np.exp(R_mat) * e_hat) / scale_2
            
            I2 = -1 * ξₚ * np.log(scale_2)

            def J2_without_e_fnc(x):
                return xi_d * np.exp(R_mat) * q2_tilde_fnc(x) * (γ1 * x + γ2 * F_mat * x ** 2 + γ2_plus * x * (x * F_mat - F̄) ** (power - 1) * ((x * F_mat - F̄) >= 0)) * norm.pdf(x,β𝘧,np.sqrt(σᵦ))
            
            J2_without_e = quad_int(J2_without_e_fnc, a, b, n, 'legendre')
            J2_with_e = J2_without_e * e_hat

            self.R2 = (I2 - J2_with_e) / ξₚ
            self.π̃2 = (1 - self.weight) * np.exp(-1 / ξₚ * I2)
            π̃1_norm = self.π̃1 / (self.π̃1 + self.π̃2)
            π̃2_norm = 1 - π̃1_norm

            expec_e_sum = (π̃1_norm * J1_without_e + π̃2_norm * J2_without_e)

            B1 = v0_dr - v0_df * np.exp(R_mat) - expec_e_sum
            C1 = -δ * κ
            self.e = -C1 / B1
            e_star = self.e

            J1 = J1_without_e * e_star
            J2 = J2_without_e * e_star

            I_term = -1 * ξₚ * np.log(self.π̃1 + self.π̃2)

            self.R1 = (I1 - J1) / ξₚ
            self.R2 = (I2 - J2) / ξₚ
            drift_distort = (π̃1_norm * J1 + π̃2_norm * J2)

            if self.weight == 0 or self.weight == 1:
                self.RE = π̃1_norm * self.R1 + π̃2_norm * self.R2
            else:
                self.RE = π̃1_norm * self.R1 + π̃2_norm * self.R2 + π̃1_norm * np.log(
                    π̃1_norm / self.weight) + π̃2_norm * np.log(π̃2_norm / (1 - self.weight))

            RE_total = ξₚ * self.RE

            A = -δ * np.ones(R_mat.shape)
            B_r = -e_star + ψ0 * (self.j ** ψ1) - 0.5 * (σ𝘳 ** 2)
            B_f = e_star * np.exp(R_mat)
            B_k = μ̄ₖ + ϕ0 * np.log(1 + self.i * ϕ1) - 0.5 * (σ𝘬 ** 2)
            C_rr = 0.5 * σ𝘳 ** 2 * np.ones(R_mat.shape)
            C_ff = np.zeros(R_mat.shape)
            C_kk = 0.5 * σ𝘬 ** 2 * np.ones(R_mat.shape)
            D = δ * κ * np.log(e_star) + δ * κ * R_mat + δ * (1 - κ) * (np.log(α - self.i - self.j * np.exp(R_mat - K_mat)) + K_mat) + I_term #  + drift_distort + RE_total

            out = self.__PDESolver__(A, B_r, B_f, B_k, C_rr, C_ff, C_kk, D, 'False Trasient')
            
            out_comp = out[2].reshape(self.v0.shape,order = "F")

            PDE_rhs = A * self.v0 + B_r * v0_dr + B_f * v0_df + B_k * v0_dk + C_rr * v0_drr + C_kk * v0_dkk + C_ff * v0_dff + D
            PDE_Err = np.max(abs(PDE_rhs))
            FC_Err = np.max(abs((out_comp - self.v0)))
            if episode % 100 == 0:
                print("Episode {:d}: PDE Error: {:.10f}; False Transient Error: {:.10f}; Iterations: {:d}; CG Error: {:.10f}" .format(episode, PDE_Err, FC_Err, out[0], out[1]))
            episode += 1
            self.v0 = out_comp
            if self.status == 0:
                self.status = 1

        self.expec_e_sum = expec_e_sum

        self.status = 2
        print("Episode {:d}: PDE Error: {:.10f}; False Transient Error: {:.10f}; Iterations: {:d}; CG Error: {:.10f}" .format(episode, PDE_Err, FC_Err, out[0], out[1]))
        print("--- %s seconds ---" % (time.time() - start_time))

    def Simulate(self, method = 'Linear'):
        # Can this be customized ???
        T = 100
        pers = 4 * T
        dt = T / pers
        nDims = 5
        its = 1

        # Unpacking necesssary variables
        α = self.modelParams['α']
        ξₚ = self.modelParams['ξₚ']
        ψ0 = self.modelParams['ψ0']
        ψ1 = self.modelParams['ψ1']
        ϕ0 = self.modelParams['ϕ0']
        ϕ1 = self.modelParams['ϕ1']
        μ̄ₖ = self.modelParams['μ̄ₖ'] 

        power = self.modelParams['power']
        γ1 = self.modelParams['γ1']
        γ2 = self.modelParams['γ2']
        γ2_plus = self.modelParams['γ2_plus']
        σ1 = self.modelParams['σ1']
        σ2 = self.modelParams['σ2']
        ρ12 = self.modelParams['ρ12'] 
        F̄ = self.modelParams['F̄']
        crit = self.modelParams['crit']
        F0 = self.modelParams['F0']
        β𝘧 = self.modelParams['β𝘧']
        σᵦ = self.modelParams['σᵦ']
        γ̄2_plus = self.γ̄2_plus
        hR = self.hR
        hK = self.hK
        hF = self.hF
        n = self.n
        quadrature = self.quadrature
        xi_d = self.modelParams['xi_d']


        R_mat = self.R_mat
        F_mat = self.F_mat
        K_mat = self.K_mat

        a = β𝘧 - 5 * np.sqrt(σᵦ)
        b = β𝘧 + 5 * np.sqrt(σᵦ)

        gridpoints = (self.R, self.F, self.K)

        v0_dr = finiteDiff(self.v0,0,1,hR,1e-8) 
        v0_df = finiteDiff(self.v0,1,1,hF)
        v0_dk = finiteDiff(self.v0,2,1,hK)

        e_func_r = GridInterp(gridpoints, self.e, method)
        def e_func(x):
            return e_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        j_func_r = GridInterp(gridpoints, self.j, method)
        def j_func(x):
            return max(j_func_r.get_value(np.log(x[0]), x[2], np.log(x[1])), 0)

        i_func_r = GridInterp(gridpoints, self.i, method)
        def i_func(x):
            return i_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        v_drfunc_r = GridInterp(gridpoints, v0_dr, method)
        def v_drfunc(x):
            return v_drfunc_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        v_dtfunc_r = GridInterp(gridpoints, v0_df, method)
        def v_dtfunc(x):
            return v_dtfunc_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        v_dkfunc_r = GridInterp(gridpoints, v0_dk, method)
        def v_dkfunc(x):
            return v_dkfunc_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        v_func_r = GridInterp(gridpoints, self.v0, method)
        def v_func(x):
            return v_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        pi_tilde_1_func_r = GridInterp(gridpoints, self.π̃1 / (self.π̃1 + self.π̃2), method)
        def pi_tilde_1_func(x):
            return pi_tilde_1_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        pi_tilde_2_func_r = GridInterp(gridpoints, self.π̃2 / (self.π̃1 + self.π̃2), method)
        def pi_tilde_2_func(x):
            return pi_tilde_2_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        def scale_2_fnc(x):
            return np.exp(-1 / ξₚ * xi_d * (γ1 * x + γ2 * x ** 2 * F_mat + γ2_plus * x * (x * F_mat - F̄) ** (power - 1) * ((x * F_mat - F̄) >= 0)) * np.exp(R_mat) * self.e)  * norm.pdf(x,β𝘧,np.sqrt(σᵦ))
        
        scale_2 = quad_int(scale_2_fnc, a, b, n, 'legendre')

        def q2_tilde_fnc(x):
            return np.exp(-1 / ξₚ * xi_d * (γ1 * x + γ2 * x ** 2 * F_mat + γ2_plus * x * (x * F_mat - F̄) ** (power - 1) * ((x * F_mat - F̄) >= 0)) * np.exp(R_mat) * self.e) / scale_2
            
        def base_model_drift_func(x):
            return np.exp(R_mat) * self.e * (γ1 * x + γ2 * x ** 2 * F_mat + self.γ̄2_plus * x * (x * F_mat - F̄) ** (power - 1) * ((x * F_mat - F̄) >= 0)) * norm.pdf(x,β𝘧,np.sqrt(σᵦ))
        base_model_drift =  quad_int(base_model_drift_func, a, b, n, 'legendre')

        mean_nordhaus = self.β̃1
        lambda_tilde_nordhaus = self.λ̃1
        nordhaus_model_drift = (γ1 * mean_nordhaus + γ2 * (1 / lambda_tilde_nordhaus + mean_nordhaus ** 2) * F_mat) * np.exp(R_mat) * self.e

        def weitzman_model_drift_func(x):
            return np.exp(R_mat) * self.e * q2_tilde_fnc(x) * (γ1 * x + γ2 * x ** 2 * F_mat + γ̄2_plus * x * (x * F_mat - F̄ ) ** (power - 1) * ((x * F_mat - F̄) >= 0)) * norm.pdf(x,β𝘧,np.sqrt(σᵦ))
        weitzman_model_drift = quad_int(weitzman_model_drift_func, a, b, n, 'legendre')

        nordhaus_drift_func_r = GridInterp(gridpoints, nordhaus_model_drift, method)
        def nordhaus_drift_func(x):
            return nordhaus_drift_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        weitzman_drift_func_r = GridInterp(gridpoints, weitzman_model_drift, method)
        def weitzman_drift_func(x):
            return weitzman_drift_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        base_drift_func_r = GridInterp(gridpoints, base_model_drift, method)
        def base_drift_func (x): 
            return base_drift_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        # function handles
        def muR(x):
            return -e_func(x) + ψ0 * j_func(x) ** ψ1
        def muK(x): 
            return (μ̄k + ϕ0 * np.log(1 + i_func(x) * ϕ1))
        def muF(x):
            return e_func(x) * x[0]
        def muD_base(x):
            return base_drift_func(x)
        def muD_tilted(x):
            return pi_tilde_1_func(x) * nordhaus_drift_func(x) + (1 - pi_tilde_1_func(x)) * weitzman_drift_func(x)

        def sigmaR(x):
            return np.zeros(x[:5].shape)
        def sigmaK(x):
            return np.zeros(x[:5].shape)
        def sigmaF(x):
            return np.zeros(x[:5].shape)
        def sigmaD(x):
            return np.zeros(x[:5].shape)

        # initial points
        R_0 = 650
        K_0 = 80 / α
        F_0 = 870 - 580
        initial_val = np.array([R_0, K_0, F_0])
        D_0_base = muD_base(initial_val)
        D_0_tilted = muD_tilted(initial_val)

        # Set bounds
        R_max_sim = np.exp(max(self.R))
        K_max_sim = np.exp(max(self.K))
        F_max_sim = max(self.F)
        D_max_sim = 5.0

        R_min_sim = np.exp(min(self.R))
        K_min_sim = np.exp(min(self.K))
        F_min_sim = min(self.F)
        D_min_sim = -5

        upperbounds = np.array([R_max_sim, K_max_sim, F_max_sim, D_max_sim, D_max_sim])
        lowerbounds = np.array([R_min_sim, K_min_sim, F_min_sim, D_min_sim, D_min_sim])

        self.hists = np.zeros([pers, nDims, its])
        # hists = hists.copy()
        self.e_hists = np.zeros([pers,its])
        # e_hists = e_hists.copy()
        self.j_hists = np.zeros([pers,its])
        # j_hists = j_hists.copy()
        self.i_hists = np.zeros([pers,its])
        # i_hists = i_hists.copy()

        v_dr_hists = np.zeros([pers,its])
        v_dt_hists = np.zeros([pers,its])
        v_dk_hists = np.zeros([pers,its])
        v_hists = np.zeros([pers,its])

        for iters in range(0,its):
            hist = np.zeros([pers,nDims])
            e_hist = np.zeros([pers,1])
            i_hist = np.zeros([pers,1])
            j_hist = np.zeros([pers,1])
            
            v_dr_hist = np.zeros([pers,1])
            v_dt_hist = np.zeros([pers,1])
            v_dk_hist = np.zeros([pers,1])
            v_hist = np.zeros([pers,1])
            
            hist[0,:] = [R_0, K_0, F_0, D_0_base, D_0_tilted]
            e_hist[0] = e_func(hist[0,:]) * hist[0,0]
            i_hist[0] = i_func(hist[0,:]) * hist[0,1]
            j_hist[0] = j_func(hist[0,:]) * hist[0,0]
            v_dr_hist[0] = v_drfunc(hist[0,:])
            v_dt_hist[0] = v_dtfunc(hist[0,:])
            v_dk_hist[0] = v_dkfunc(hist[0,:])
            v_hist[0] = v_func(hist[0,:])
            
            for tm in range(1,pers):
                shock = norm.rvs(0,np.sqrt(dt),nDims)
                # print(muR(hist[tm-1,:]))
                hist[tm,0] = cap(hist[tm-1,0] * np.exp((muR(hist[tm-1,:])- 0.5 * sum((sigmaR(hist[tm-1,:])) ** 2))* dt + sigmaR(hist[tm-1,:]).dot(shock)),lowerbounds[0], upperbounds[0])
                hist[tm,1] = cap(hist[tm-1,1] * np.exp((muK(hist[tm-1,:])- 0.5 * sum((sigmaK(hist[tm-1,:])) ** 2))* dt + sigmaK(hist[tm-1,:]).dot(shock)),lowerbounds[1], upperbounds[1])
                hist[tm,2] = cap(hist[tm-1,2] + muF(hist[tm-1,:]) * dt + sigmaF(hist[tm-1,:]).dot(shock), lowerbounds[2], upperbounds[2])
                hist[tm,3] = cap(hist[tm-1,3] + muD_base(hist[tm-1,:]) * dt + sigmaD(hist[tm-1,:]).dot(shock), lowerbounds[3], upperbounds[3])
                hist[tm,4] = cap(hist[tm-1,4] + muD_tilted(hist[tm-1,:]) * dt + sigmaD(hist[tm-1,:]).dot(shock), lowerbounds[4], upperbounds[4])
                
                e_hist[tm] = e_func(hist[tm-1,:]) * hist[tm-1,0]
                i_hist[tm] = i_func(hist[tm-1,:]) * hist[tm-1,1]
                j_hist[tm] = j_func(hist[tm-1,:]) * hist[tm-1,0]
                
                v_dr_hist[tm] = v_drfunc(hist[tm-1,:])
                v_dt_hist[tm] = v_dtfunc(hist[tm-1,:])
                v_dk_hist[tm] = v_dkfunc(hist[tm-1,:])
                v_hist[tm] = v_func(hist[tm-1,:])
                
            self.hists[:,:,iters] = hist
            self.e_hists[:,[iters]] = e_hist
            self.i_hists[:,[iters]] = i_hist
            self.j_hists[:,[iters]] = j_hist
            
            v_dr_hists[:,[iters]] = v_dr_hist
            v_dt_hists[:,[iters]] = v_dt_hist
            v_dk_hists[:,[iters]] = v_dk_hist
            v_hists[:,[iters]] = v_hist

    def SCCDecompose(self, AmbiguityNeutral = False, method = 'Linear'):
        if AmbiguityNeutral:
            α  = self.modelParams['α']
            κ  = self.modelParams['κ']
            ξₚ = self.modelParams['ξₚ']

            SCC = 1000 *  (κ / (1- κ) * (α * self.hists[:,1,0] - self.i_hists[:,0] - self.j_hists[:,0]) / self.e_hists[:,0])
            self.SCCs['SCC'] = SCC
        else:
            δ  = self.modelParams['δ']
            κ  = self.modelParams['κ']
            σ𝘨 = self.modelParams['σ𝘨']
            σ𝘬 = self.modelParams['σ𝘬']
            σ𝘳 = self.modelParams['σ𝘳']
            α  = self.modelParams['α']
            ϕ0 = self.modelParams['ϕ0']
            ϕ1 = self.modelParams['ϕ1']
            μ̄ₖ = self.modelParams['μ̄ₖ'] 
            ψ0 = self.modelParams['ψ0']
            ψ1 = self.modelParams['ψ1']
            power = self.modelParams['power']
            γ1 = self.modelParams['γ1']
            γ2 = self.modelParams['γ2']
            γ2_plus = self.modelParams['γ2_plus']
            σ1 = self.modelParams['σ1']
            σ2 = self.modelParams['σ2']
            ρ12 = self.modelParams['ρ12'] 
            F̄ = self.modelParams['F̄']
            crit = self.modelParams['crit']
            F0 = self.modelParams['F0']
            ξₚ = self.modelParams['ξₚ']
            β𝘧 = self.modelParams['β𝘧']
            σᵦ = self.modelParams['σᵦ']
            λ = self.modelParams['λ']
            σ𝘥 = self.modelParams['σ𝘥']
            xi_d = self.modelParams['xi_d']
            γ̄2_plus = self.γ̄2_plus
            hR = self.hR
            hK = self.hK
            hF = self.hF
            n = self.n
            pers = 400 # can modify
            its = 1

            R_mat = self.R_mat
            F_mat = self.F_mat
            K_mat = self.K_mat

            a = β𝘧 - 5 * np.sqrt(σᵦ)
            b = β𝘧 + 5 * np.sqrt(σᵦ)
            # Base model
            def base_model_flow_func(x):
                return (γ2 * x ** 2 + γ̄2_plus * x ** 2 * ((x * F_mat - F̄) >=0)) * np.exp(R_mat) * self.e *  norm.pdf(x,β𝘧,np.sqrt(σᵦ))
            base_model_flow = quad_int(base_model_flow_func, a, b, n, 'legendre')
            flow_base = base_model_flow

            # input for solver

            A = -δ * np.ones(R_mat.shape)
            B_r = -self.e + ψ0 * (self.j ** ψ1) - 0.5 * (σ𝘳 ** 2)
            B_k = μ̄ₖ + ϕ0 * np.log(1 + self.i * ϕ1) - 0.5 * (σ𝘬 ** 2)
            B_f = self.e * np.exp(R_mat)
            C_rr = 0.5 * σ𝘳 ** 2 * np.ones(R_mat.shape)
            C_kk = 0.5 * σ𝘬 ** 2 * np.ones(R_mat.shape)
            C_ff = np.zeros(R_mat.shape)
            D = flow_base

            out = self.__PDESolver__(A, B_r, B_f, B_k, C_rr, C_ff, C_kk, D, 'Feyman Kac')
            v0_base = out[2].reshape(self.v0.shape, order="F")
            self.v0_base = v0_base

            v0_dr_base = finiteDiff(v0_base,0,1,hR,1e-8) 
            v0_df_base = finiteDiff(v0_base,1,1,hF)
            v0_dk_base = finiteDiff(v0_base,2,1,hK)

            v0_drr_base = finiteDiff(v0_base,0,2,hR)
            v0_dff_base = finiteDiff(v0_base,1,2,hF)
            v0_dkk_base = finiteDiff(v0_base,2,2,hK)

            PDE_rhs = A * v0_base + B_r * v0_dr_base + B_f * v0_df_base + B_k * v0_dk_base + C_rr * v0_drr_base + C_kk * v0_dkk_base + C_ff * v0_dff_base + D
            PDE_Err = np.max(abs(PDE_rhs))
            print("Feyman Kac Base Model Solved. PDE Error: %f; Iterations: %d; CG Error: %f" %(PDE_Err, out[0], out[1]))

            # Worst Model
            mean_nordhaus = self.β̃1
            lambda_tilde_nordhaus = self.λ̃1

            def scale_2_fnc(x):
                return np.exp(-1 / ξₚ * xi_d * (γ1 * x + γ2 * x ** 2 * F_mat + γ2_plus * x * (x * F_mat - F̄) ** (power - 1) * ((x * F_mat - F̄) >= 0)) * np.exp(R_mat) * self.e)  * norm.pdf(x,β𝘧,np.sqrt(σᵦ))
            
            scale_2 = quad_int(scale_2_fnc, a, b, n, 'legendre')

            def q2_tilde_fnc(x):
                return np.exp(-1 / ξₚ * xi_d * (γ1 * x + γ2 * x ** 2 * F_mat + γ2_plus * x * (x * F_mat - F̄) ** (power - 1) * ((x * F_mat - F̄) >= 0)) * np.exp(R_mat) * self.e) / scale_2

            nordhaus_model_flow = (γ2 * (1 / lambda_tilde_nordhaus + mean_nordhaus ** 2)) * np.exp(R_mat) * self.e 
            # weitzman_model_flow_func = @(x) q2_tilde_1_fnc(x) .*(gamma_2.*x.^2 +gamma_2_plus.*x.^2.*((x.*t_mat-f_bar)>=0)).*exp(r_mat).*e .*normpdf(x,beta_f,sqrt(var_beta_f));
            def weitzman_model_flow_func(x): 
                return q2_tilde_fnc(x) * (γ2 * x ** 2 + γ2_plus * x ** 2 * ((x * F_mat - F̄) >= 0 )) * np.exp(R_mat) * self.e * norm.pdf(x,β𝘧,np.sqrt(σᵦ))
            weitzman_model_flow = quad_int(weitzman_model_flow_func, a, b, n, 'legendre')

            I1 = self.a1 - 0.5 * np.log(λ) * ξₚ + 0.5 * np.log(self.λ̃1) * ξₚ + 0.5 * λ * β𝘧 ** 2 * ξₚ - 0.5 * self.λ̃1 * (self.β̃1) ** 2 * ξₚ
            I2 = -1 * ξₚ * np.log(scale_2)
            π̃1 = (self.weight) * np.exp(-1 / ξₚ * I1)
            π̃2 = (1 - self.weight) * np.exp(-1 / ξₚ * I2)
            π̃1_norm = π̃1 / (π̃1 + π̃2)
            π̃2_norm = 1 - π̃1_norm

            flow_tilted = π̃1_norm * nordhaus_model_flow + π̃2_norm * weitzman_model_flow

            A = -δ * np.ones(R_mat.shape)
            B_r = -self.e + ψ0 * (self.j ** ψ1) - 0.5 * (σ𝘳 ** 2)
            B_k = μ̄ₖ + ϕ0 * np.log(1 + self.i * ϕ1) - 0.5 * (σ𝘬 ** 2)
            B_f = self.e * np.exp(R_mat)
            C_rr = 0.5 * σ𝘳 ** 2 * np.ones(R_mat.shape)
            C_kk = 0.5 * σ𝘬 ** 2 * np.ones(R_mat.shape)
            C_ff = np.zeros(R_mat.shape)
            D = flow_tilted

            out = self.__PDESolver__(A, B_r, B_f, B_k, C_rr, C_ff, C_kk, D, 'Feyman Kac')
            v0_worst = out[2].reshape(self.v0.shape, order="F")
            self.v0_worst = v0_worst

            v0_dr_worst = finiteDiff(v0_worst,0,1,hR,1e-8) 
            v0_df_worst = finiteDiff(v0_worst,1,1,hF)
            v0_dk_worst = finiteDiff(v0_worst,2,1,hK)

            v0_drr_worst = finiteDiff(v0_worst,0,2,hR)
            v0_dff_worst = finiteDiff(v0_worst,1,2,hF)
            v0_dkk_worst = finiteDiff(v0_worst,2,2,hK)

            PDE_rhs = A * v0_worst + B_r * v0_dr_worst + B_f * v0_df_worst + B_k * v0_dk_worst + C_rr * v0_drr_worst + C_kk * v0_dkk_worst + C_ff * v0_dff_worst + D
            PDE_Err = np.max(abs(PDE_rhs))
            print("Feyman Kac Worst Case Model Solved. PDE Error: %f; Iterations: %d; CG Error: %f" %(PDE_Err, out[0], out[1]))

            
            # SCC decomposition

            v0_dr = finiteDiff(self.v0,0,1,hR,1e-8) 
            v0_df = finiteDiff(self.v0,1,1,hF)
            v0_dk = finiteDiff(self.v0,2,1,hK)

            v0_drr = finiteDiff(self.v0,0,2,hR)
            v0_dff = finiteDiff(self.v0,1,2,hF)
            v0_dkk = finiteDiff(self.v0,2,2,hK)

            gridpoints = (self.R, self.F, self.K)  # can modify

            MC = δ * (1-κ) / (α * np.exp(K_mat) - self.i * np.exp(K_mat) - self.j * np.exp(R_mat))
            ME = δ * κ / (self.e * np.exp(R_mat))
            SCC = 1000 * ME / MC
            SCC_func_r = GridInterp(gridpoints, SCC, method)

            def SCC_func(x): 
                return SCC_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

            ME1 = v0_dr * np.exp(-R_mat)
            SCC1 = 1000 * ME1 / MC
            SCC1_func_r = GridInterp(gridpoints, SCC1, method)
            def SCC1_func(x):
                return SCC1_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

            ME2_base = (1-κ) * v0_base
            SCC2_base = 1000 * ME2_base / MC
            SCC2_base_func_r = GridInterp(gridpoints, SCC2_base, method)
            def SCC2_base_func(x):
                return SCC2_base_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

            def V_d_baseline_func(x):
                return xi_d * (γ1 * x + γ2 * F_mat * x** 2 +
                                self.γ̄2_plus * x * (x * F_mat - F̄) * (power - 1)
                                * ((x * F_mat - F̄) >= 0 )) * norm.pdf(x, β𝘧, np.sqrt(σᵦ))
            V_d_baseline = quad_int(V_d_baseline_func, a, b, n, 'legendre')
            ME2b = -V_d_baseline
            SCC2_V_d_baseline = 1000 * ME2b / MC
            SCC2_V_d_baseline_func_r = GridInterp(gridpoints, SCC2_V_d_baseline, method)
            def SCC2_V_d_baseline_func(x):
                return SCC2_V_d_baseline_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

            ME2_tilt = (1-κ) * v0_worst
            SCC2_tilt = 1000 * ME2_tilt / MC
            SCC2_tilt_func_r = GridInterp(gridpoints, SCC2_tilt, method)
            def SCC2_tilt_func(x):
                return SCC2_tilt_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))


            ME2b = -self.expec_e_sum * np.exp(-R_mat)
            SCC2_V_d_tilt_ = 1000 * ME2b / MC
            SCC2_V_d_tilt_func_r = GridInterp(gridpoints, SCC2_V_d_tilt_, method)
            def SCC2_V_d_tilt_func(x):
                return SCC2_V_d_tilt_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))


            SCC_values = np.zeros([pers,its])
            SCC1_values = np.zeros([pers,its])
            SCC2_base_values = np.zeros([pers,its])
            SCC2_tilt_values = np.zeros([pers,its])
            SCC2_V_d_baseline_values = np.zeros([pers,its])
            SCC2_V_d_tilt_values = np.zeros([pers,its])

            for tm in range(pers):
                for path in range(its):   # path is its?
                    SCC_values[tm, path] = SCC_func(self.hists[tm,:,path])
                    SCC1_values[tm, path] = SCC1_func(self.hists[tm,:,path])
                    SCC2_base_values[tm, path] = SCC2_base_func(self.hists[tm,:,path]) 
                    SCC2_tilt_values[tm, path] = SCC2_tilt_func(self.hists[tm,:,path])
                    SCC2_V_d_baseline_values[tm, path] = SCC2_V_d_baseline_func(self.hists[tm,:,path])
                    SCC2_V_d_tilt_values[tm, path] = SCC2_V_d_tilt_func(self.hists[tm,:,path])
                    
            SCC_total = np.mean(SCC_values,axis = 1)
            SCC_private = np.mean(SCC1_values,axis = 1)
            SCC2_FK_base = np.mean(SCC2_base_values,axis = 1)
            SCC2_FK_tilt = np.mean(SCC2_tilt_values,axis = 1)
            SCC2_V_d_baseline = np.mean(SCC2_V_d_baseline_values,axis = 1)
            SCC2_V_d_tilt = np.mean(SCC2_V_d_tilt_values,axis = 1)

            self.SCCs['SCC'] = SCC_total
            self.SCCs['SCC1'] = SCC_private
            self.SCCs['SCC2'] = SCC2_FK_base + SCC2_V_d_baseline
            self.SCCs['SCC3'] = SCC2_V_d_tilt - SCC2_V_d_baseline + SCC2_FK_tilt - SCC2_FK_base

    def computeProbs(self, damageSpec = 'High', method = 'Linear'):
        # unpacking necessary variables
        
        β𝘧 = self.modelParams['β𝘧']
        σᵦ = self.modelParams['σᵦ']
        gridpoints = (self.R, self.F, self.K)
        pers = 400
        n = self.n
        ξₚ = self.modelParams['ξₚ']
        power = self.modelParams['power']
        γ1 = self.modelParams['γ1']
        γ2 = self.modelParams['γ2']
        γ2_plus = self.modelParams['γ2_plus']
        F̄ = self.modelParams['F̄']
        F0 = self.modelParams['F0']
        xi_d = self.modelParams['xi_d']

        # probabilities
        a = β𝘧 - 5 * np.sqrt(σᵦ)
        b = β𝘧 + 5 * np.sqrt(σᵦ)
        a_10std = β𝘧 - 10 * np.sqrt(σᵦ)
        b_10std = β𝘧 + 10 * np.sqrt(σᵦ)

        RE_func_r = GridInterp(gridpoints, self.RE, method)
        def RE_func(x):
            return RE_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        e_func_r = GridInterp(gridpoints, self.e, method)
        def e_func(x):
            return e_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        pi_tilde_1_func_r = GridInterp(gridpoints, self.π̃1, method)
        def pi_tilde_1_func(x):
            return pi_tilde_1_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        lambda_tilde_1_func_r = GridInterp(gridpoints, self.λ̃1, method)
        def lambda_tilde_1_func(x):
            return lambda_tilde_1_func_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        beta_tilde_1_r = GridInterp(gridpoints, self.β̃1, method)
        def beta_tilde_1_func(x):
            return beta_tilde_1_r.get_value(np.log(x[0]), x[2], np.log(x[1]))

        RE_plot = np.zeros(pers)
        weight_plot = np.zeros(pers)
        beta_f_space = np.linspace(a_10std,b_10std,200)
        self.beta_f_space = beta_f_space

        #Relative Entropy

        if damageSpec == 'low':
            nordhaus_mean = np.zeros(pers)
            nordhaus_std = np.zeros(pers)

            for tm in range(pers):
                RE_plot[tm] = RE_func(self.hists[tm,:,0])
                weight_plot[tm] = pi_tilde_1_func(self.hists[tm,:,0])
                nordhaus_mean[tm] = beta_tilde_1_func(self.hists[tm,:,0])
                nordhaus_std[tm] = 1 / np.sqrt(lambda_tilde_1_func(self.hists[tm,:,0]))

            self.REs['RE'] = RE_plot
            self.REs['Weights'] = weight_plot
            self.REs['Shifted Mean'] = nordhaus_mean
            self.REs['Shifted Std'] = nordhaus_std

        else:
            for tm in range(pers):
                RE_plot[tm] = RE_func(self.hists[tm,:,0])
                weight_plot[tm] = pi_tilde_1_func(self.hists[tm,:,0])

            self.REs['RE'] = RE_plot
            self.REs['Weights'] = weight_plot


        # probabilities (R,K,F)
        original_dist = norm.pdf(beta_f_space, β𝘧, np.sqrt(σᵦ))
        self.Dists['Original'] = original_dist

        for tm in [1,100,200,300,400]:
            R0 = self.hists[tm-1,0,0]
            K0 = self.hists[tm-1,1,0]
            F0 = self.hists[tm-1,2,0]

            # Weitzman
            def scale_2_fnc_prob(x):
                return np.exp(-1 / ξp * xi_d * (γ1 * x + γ2 * x ** 2 *  F0 + γ2_plus * x * (x * F0 - F̄) ** (power - 1) * ((x * F0 - F̄) >= 0)) * R0 * e_func([R0, K0, F0])) * norm.pdf(x, β𝘧, np.sqrt(σᵦ))
            scale_2_prob = quad_int(scale_2_fnc_prob, a, b, n, 'legendre')

            q2_tilde_fnc_prob = np.exp(-1 / ξp * xi_d * (γ1 * beta_f_space + γ2 * beta_f_space ** 2 * F0 + γ2_plus * beta_f_space * (beta_f_space * F0 - F̄) ** (power - 1) * ((beta_f_space * F0 - F̄) >= 0)) * R0* e_func([R0, K0, F0])) / scale_2_prob * norm.pdf(beta_f_space, β𝘧, np.sqrt(σᵦ))
            weitzman = q2_tilde_fnc_prob

            # Nordhaus
            mean_distort_nordhaus = beta_tilde_1_func([R0, K0, F0]) - β𝘧
            lambda_tilde_nordhaus = lambda_tilde_1_func([R0, K0, F0])
            nordhaus = norm.pdf(beta_f_space, mean_distort_nordhaus + β𝘧, 1 / np.sqrt(lambda_tilde_nordhaus))

            # weights
            Dists_weight = pi_tilde_1_func([R0, K0, F0])
            if damageSpec == 'High':
                self.Dists['Weitzman_year' + str(int((tm) / 4))] = weitzman
            elif damageSpec == 'Low':
                self.Dists['Nordhaus_year' + str(int((tm) / 4))] = nordhaus
            elif damageSpec == 'Weighted':
                self.Dists['Weitzman_year' + str(int((tm) / 4))] = weitzman
                self.Dists['Nordhaus_year' + str(int((tm) / 4))] = nordhaus
                self.Dists['Weighted_year' + str(int((tm) / 4))] = nordhaus * Dists_weight + weitzman * (1 - Dists_weight)

    def test(self):
        α = self.α
        α += 1



if __name__ == "__main__":
    # for key,val in defaultParams.items():
    #   print(key,val)
    print(defaultParams['μ̄ₖ'])


    print("----------------HJB-------------------")

    # old_string = "didn't work"
    # new_string = "worked"
    # function()

    if not os.path.isfile('./lowdmg.pickle'):
        m = climateModel(defaultParams, solverSpecification)
        m.solveHJB('Low')
        res = loadmat('./MATLAB_Data/HJB_NonLinPref_Cumu_NoUn')
        print(np.max(abs(m.v0 - res['out_comp'])))
        with open("lowdmg.pickle", "wb") as file_:
            pickle.dump(m, file_, -1)
    else:
        m = pickle.load(open("lowdmg.pickle", "rb", -1))


    print("-------------Simulation---------------")
    m.Simulate()
    print(m.hists[-1,:,0])
    res = loadmat('./MATLAB_Data/HJB_NonLinPref_Cumu_NoUn')
    print(np.max(abs(m.j - res['f'])))

    print("------------SCCDecompose--------------")
    m.SCCDecompose(AmbiguityNeutral = True)
    # print(m.SCCs['SCC'])

    print("------------ComputeProbs--------------")

    # m.computeProbs()
    # print(m.Dists['Nordhaus_year100'])

