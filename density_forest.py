

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os 

from df_help import *

from grid import Grid
from tree import Tree
from node import NodeGauss, NodeKDE
import argparse

from pylab import *


argparser = argparse.ArgumentParser(
    description='randomforest-density: density estimation using random forests.')


argparser.add_argument(
    '-l',
    '--leaf',
    help='Choose what leaf estimator to use'
    ' (Gaussian [\'gauss\'] or KDE [\'kde\'])',
    default='gauss')

argparser.add_argument(
    '-d',
    '--data',
    help='Path to data (.npy file, shape (sample_zie, 2)).',
    default='')

argparser.add_argument(
    '-g',
    '--granularity',
    help='Number of division for the Grid',
    default=100)




args = argparser.parse_args()
assert args.leaf in ['kde', 'gauss'], "Pass valid leaf estimator"


LEAF_DICT = {
            'kde': NodeKDE,
            'gauss': NodeGauss
} 

LEAF_TYPE = args.leaf
MODE = 'est' if args.data else 'demo'
DATA_PATH = args.data
DIVS = args.granularity

def gauss_entropy_func(S):
    """
    Gaussian differential entropy (ignoring constant terms since 
    we're interested in the delta).
    """
    return np.log(np.linalg.det(np.cov(S, rowvar=False)) + 1e-8)


class DensityForest:
    """
    Class for density forest, compute entropy threshold for stop condition, then build and
    train forest of trees with randomness rho.
    """

    def __init__(self, data, grid_obj, f_size, rho=1.):
        
        self.data = data
        self.f_size = f_size

        self.node_class = NodeGauss
        self.entropy_func = gauss_entropy_func

        self.grid_obj = grid_obj

        self.grid = self.grid_obj.axis
        
        self.rho = rho


    def train(self):

        self.opt_entropy = self.tune_entropy_threshold(plot_debug=True)
        self.forest = self.build_forest()


    def estimate(self):

        self.dist = self.compute_density()
        return self.dist


    def compute_density(self):



        dist = []
        for j, y in enumerate(self.grid[1]):
            dist.append([])
            for i, x in enumerate(self.grid[0]):    
                dist[j].append(self.forest_output(np.array([x, y])))
        return dist
        

    def plot_density(self, fname='density_estimation.png'):

        X = self.grid[0]
        Y = self.grid[1]
        Z = self.dist

        fig = plt.figure(figsize=(12, 12))
        ax = fig.add_subplot(111)


        vmin=np.min(Z)
        vmax=np.max(Z)
        var = plt.pcolormesh(np.array(X),np.array(Y),np.array(Z), cmap=cm.Blues, vmin=vmin, vmax=vmax)
        plt.colorbar(var, ticks=np.arange(vmin, vmax, (vmax-vmin)/8))

        ax = plt.gca()

        gris = 200.0
        ax.set_facecolor((gris/255, gris/255, gris/255))

        #ax.scatter(*zip(*self.data), alpha=.5, c='k', s=10., lw=0)

        plt.xlim(np.min(X), np.max(X))
        plt.ylim(np.min(Y), np.max(Y))
        plt.grid()

        ax.set_title('rho = %s, |T| = %d, max_entropy = %.2f'%(self.rho, self.f_size, self.opt_entropy))

        fig.savefig(fname, format='png')
        plt.close()



    def forest_output(self, x):

        result = []
        for i, t in self.forest.items():
            result.append( t.output(x) )

        return np.mean(result)



    def build_forest(self):

        forest = {}

        for t in range(self.f_size):
            forest[t] = Tree(self, rho=self.rho)
            forest[t].tree_leaf_plots(fname='tree_opt%s.png'%t)
        

        path = os.getcwd() + '/plots/'
        mkdir_p(path)


        fig = plt.figure(figsize=(10,10))
        ax = fig.add_subplot(111)
        
        if MODE == 'demo':
            color = ['lightcoral', 'dodgerblue', 'mediumseagreen', 'darkorange']

            for t in range(self.f_size):
                print(len(forest[t].leaf_nodes))
                for c, n in enumerate(forest[t].leaf_nodes):

                    [[i1, i2], [j1, j2]] = n.quad
                    x1, x2 = self.grid[0][i1], self.grid[0][i2]
                    y1, y2 = self.grid[1][j1], self.grid[1][j2]
                    
                    ax.fill_between([x1,x2], y1, y2, alpha=.15, color=color[c])
     
            pd.DataFrame(self.data, columns=['x', 'y']).plot(ax=ax, x='x', y='y', kind='scatter', lw=0, alpha=.6, s=20, c='k')
            plt.savefig(path + 'combined.png', format='png')
            plt.close()


        return forest


    # Implement Online L-curve optimization like EWMA to get rid of input depth
    def tune_entropy_threshold(self, n=5, depth=6, plot_debug=False):
        """
        Compute mean optimal entropy based on L-curve elbow method.
        """
        
        e_arr = []
        for i in range(n):
            
            var = Tree(self, rho=.5, depth=depth)
            e_arr += [pair + [i] for pair in var.entropy_gain_evol]

            var.domain_splits_plots(subpath='%s/'%i)

        entropy_evol = pd.DataFrame(e_arr, columns=['depth', 'entropy', 'tree'])
        entropy_evol = entropy_evol.groupby(['tree', 'depth'])[['entropy']].mean().reset_index().pivot(columns='tree', index='depth', values='entropy').fillna(0)
        entropy_elbow_cand = entropy_evol.apply(lambda x: opt_L_curve(np.array(x.index), np.array(x)))
        
        avg_opt_entropy = entropy_elbow_cand.mean()
        if plot_debug:
            
            fig = plt.figure(figsize=(10,10))
            ax = fig.add_subplot(111)
            entropy_evol.plot(ax=ax, kind='line', alpha=.6, lw=3., title='Avg. Opt. Entropy = %.2f'%avg_opt_entropy)
            plt.savefig('evol.png', format='png')
            plt.close()

        return avg_opt_entropy




def _run_rf(data, grid_obj):

    print('Starting...')
    df_obj = DensityForest(data, grid_obj=grid_obj, f_size=5, rho=.5)
    df_obj.node_class = LEAF_DICT[LEAF_TYPE]

    print('Training...')
    df_obj.train()
    print('Estimating...')
    pdf = df_obj.estimate()
    print('Plotting...')
    df_obj.plot_density(fname='density_estimation_kde.png')

    return df_obj, pdf


def run_demo():

    params = {
                'mu' : [[0, 0], [0, 20], [50, 40], [10, -20], [20,5]],
                'cov': [[[1, 0], [0, 150]], [[90, 0], [0, 5]], [[4, 1], [1, 4]], [[40, 5], [5, 40]], [[90, 15], [15, 16]]],
                'n':[700, 20, 200, 400, 300]}
    gauss_data_obj = TestDataGauss(params=params, fname='data_new.npy', replace=False)
    gauss_data_obj.check_plot()

    df_obj, _ = _run_rf(gauss_data_obj.data, gauss_data_obj.grid_obj)

    print('Comparing...')

    comp = CompareDistributions(original=gauss_data_obj, estimate=df_obj)
    comp.vizualize_both('density_comp_kde.png', show_data=False)


def run():

    data_obj = TestDataAny(fname=DATA_PATH, partitions=DIVS)
 
    density_estimation, pdf = _run_rf(data_obj.data, data_obj.grid_obj)

    pdf_path = os.path.dirname(DATA_PATH) 
    np.save(pdf_path, pdf)

    print('\tDensity estimation function stored at: %s'%pdf_path)


if __name__ == "__main__":

    if MODE == 'demo':

        print('---------------------------')
        print('DEMO')
        print('---------------------------')
        run_demo()
    else:
        print('---------------------------')
        print('Density Estimation')
        print('---------------------------')
        run()



    '''

    params = {
            'mu' : [[0, 0], [0, 55], [20, 15], [45, 20]],
            'cov': [[[2, 0], [0, 80]], [[90, 0], [0, 5]], [[4, 0], [0, 4]], [[40, 0], [0, 40]]],
            'n':[100, 100, 100, 100]}


    var = TestDataGauss(params=params, fname='data.npy')
    '''
    '''
    foo = DensityForest(var.data, grid_obj=var.grid_obj, f_size=5, rho=.5)
    foo.train()
    foo.estimate()
    foo.plot_density()

    tri = CompareDistributions(original=var, estimate=foo)
    tri.vizualize_both('density_comp.png')
    '''

    #print(foo.forest[0].output([0, 40]))




    

