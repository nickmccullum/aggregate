"""
Distortion functions to implement spectral risk measures

May 2019: added capped log linear and tt distortions
"""

import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as ss
from scipy.interpolate import interp1d
from scipy.spatial import ConvexHull
from io import StringIO
import pandas as pd
from . utils import axiter_factory, suptitle_and_tight
from textwrap import fill
import logging

logger = logging.getLogger('aggregate')

class Distortion(object):
    """
    handles everything to do with distortion functions


    """
    # make these (mostly) immutable...avoid changing by mistake
    _available_distortions_ = ('ph', 'wang', 'cll', 'lep', 'ly', 'clin', 'dual', 'roe', 'tvar', 'wtdtvar', 'convex', 'tt')
    _has_mass_ = ('ly', 'clin', 'lep', 'roe')
    _med_names_ = ("Prop Hzrd", "Wang", 'Capd Loglin', "Lev Equiv",
                    "Lin Yield", "Capped Linear", "Dual Mom", "Const ROE", "Tail VaR", 'Wtd TVaR', "Convex Env", 'Wang-tt')
    _long_names_ = ("Proportional Hazard", "Wang-normal", 'Capped Loglinear', "Leverage Equivalent Pricing",
                    "Linear Yield", "Capped Linear", "Dual Moment", "Constant ROE", "Tail VaR", 'Weighted TVaR',
                    "Convex Envelope", 'Wang-tt')
    # TODO fix examples!
    # _available_distortions_ = ('ph', 'wang', 'cll', 'lep',  'ly', 'clin', 'dual', 'roe', 'tvar', 'wtdtvar,  'convex')
    _eg_param_1_ =              (.9,     .1,      .9,    0.25,  0.8,   1.1,   1.5,    .1,    0.15,     .15)
    _eg_param_2_ =              (.5,     .75,     .5,    0.5,   1.5,   1.8,     3,    .25,    0.5,      .5)
    # _distortion_names_ = dict(zip(_available_distortions_, _med_names_))
    _distortion_names_ = dict(zip(_available_distortions_, _long_names_))
    renamer = _distortion_names_

    # @property
    # @staticmethod
    # def renamer():
    #     return _distortion_names_

    @classmethod
    def available_distortions(cls, pricing=True, strict=True):
        """
        list of the available distortions

        :param pricing: only return list suitable for pricing, excludes tvar and convex
        :param strict: only include those without mass at zero  (pricing only)
        :return:
        """

        if pricing and strict:
            return tuple((i for i in cls._available_distortions_[:-4] if i not in cls._has_mass_))
        elif pricing:
            return cls._available_distortions_[:-2]
        else:
            return cls._available_distortions_

    def __init__(self, name, shape, r0=0.0, df=None, col_x='', col_y='', display_name=''):
        """
        create new distortion

        Tester:

            ps = np.linspace(0, 1, 201)
            for dn in agg.Distortion.available_distortions(True):
                if dn=='clin':
                    # shape param must be > 1
                    g_dist = agg.Distortion(**{'name': dn, 'shape': 1.25, 'r0': 0.02, 'df': 5.5})
                else:
                    g_dist = agg.Distortion(**{'name': dn, 'shape': 0.5, 'r0': 0.02, 'df': 5.5})
                g_dist.plot()
                g = g_dist.g
                g_inv = g_dist.g_inv

                df = pd.DataFrame({'p': ps, 'gg_inv': g(g_inv(ps)), 'g_invg': g_inv(g(ps)),
                'g': g(ps), 'g_inv': g_inv(ps)})
                print(dn)
                print("errors")
                display(df.query(' abs(gg_inv - g_invg) > 1e-5'))


        :param name: name of an available distortion, call ``Distortion.available_distortions()`` for a list
        :param shape: float or [float, float]
        :param shape: shape parameter
        :param r0: risk free or rental rate of interest
        :param df:  for convex envelope, dataframe with col_x and col_y used to parameterize or df for t
        :param col_x:
        :param col_y:
        :param display_name: over-ride name, useful for parameterized convex fix distributions
        """
        self._name = name
        self.shape = shape
        self.r0 = r0
        # when created by calibrate distortions extra info put here
        self.error = 0.0
        self.premium_target = 0.0
        self.assets = 0.0
        self.mass = 0.0
        self.df = df
        self.col_x = col_x
        self.col_y = col_y
        self.display_name = display_name

        # now make g and g_inv
        if self._name == 'ph':
            rho = self.shape
            rhoinv = 1.0 / rho
            self.has_mass = False

            # @numba.vectorize(["float64(float64)"], nopython=True, target='parallel')
            def g(x):
                return x ** rho

            def g_inv(x):
                return x ** rhoinv

        elif self._name == 'wang':
            lam = self.shape
            n = ss.norm()
            self.has_mass = False

            def g(x):
                return n.cdf(n.ppf(x) + lam)

            def g_inv(x):
                return n.cdf(n.ppf(x) - lam)

        elif self._name == 'tt':
            lam = self.shape
            t = ss.t(self.df)
            self.has_mass = False

            def g(x):
                return t.cdf(t.ppf(x) + lam)

            def g_inv(x):
                return t.cdf(t.ppf(x) - lam)

        elif self._name == 'cll':
            # capped log linear
            b = self.shape
            binv = 1 / b
            ea = np.exp(self.r0)
            a = self.r0
            self.has_mass = False

            def g(x):
                return np.where(x==0, 0, np.minimum(1, ea * x ** b))

            def g_inv(x):
                return np.where(x < 1, np.minimum(1, (x / ea) ** binv), 1)

        elif self._name == 'tvar':
            p = self.shape
            alpha = 1 / (1 - p)
            self.has_mass = False

            def g(x):
                return np.minimum(alpha * x, 1)

            def g_inv(x):
                return np.where(x < 1, x * (1 - p), 1)

        elif self._name == 'ly':
            # linear yield
            # r0 = occupancy; rk = consumption specified in list shape parameter
            rk = self.shape
            self.has_mass = (r0 > 0)
            self.mass = r0 / (1 + r0)

            def g(x):
                return np.where(x == 0, 0, (self.r0 + x * (1 + rk)) / (1 + self.r0 + rk * x))

            def g_inv(x):
                return np.maximum(0, (x * (1 + self.r0) - self.r0) / (1 + rk * (1 - x)))

        elif self._name == 'clin':
            # capped linear, needs shape > 1 to make sense...needs shape >= 1-r0 else
            # problems at 1
            sl = self.shape
            self.has_mass = (r0 > 0)
            self.mass = r0

            def g(x):
                return np.where(x == 0, 0, np.minimum(1, self.r0 + sl * x))

            def g_inv(x):
                return np.where(x <= self.r0, 0, (x - self.r0) / sl)

        elif self._name == 'roe':
            # constant roe = capped linear with shape = 1/(1+r), r0=r/(1+r)
            # r = target roe
            r = self.shape
            v = 1 / (1 + r)
            d = 1 - v
            self.has_mass = (d > 0)
            self.mass = d

            def g(x):
                return np.where(x == 0, 0, np.minimum(1, d + v * x))

            def g_inv(x):
                return np.where(x <= d, 0, (x - d) / v)

        elif self._name == 'lep':
            # leverage equivalent pricing
            # self.r0 = risk free/financing and r = risk charge (the solved parameter)
            r = self.shape
            delta = r / (1 + r)
            d = self.r0 / (1 + self.r0)
            spread = delta - d
            self.has_mass = (d > 0)
            self.mass = d

            def g(x):
                return np.where(x == 0, 0, np.minimum(1, d + (1 - d) * x + spread * np.sqrt(x * (1 - x))))

            spread2 = spread ** 2
            a = (1 - d) ** 2 + spread2

            def g_inv(y):
                mb = (2 * (y - d) * (1 - d) + spread2)  # mb = -b
                c = (y - d) ** 2
                rad = np.sqrt(mb * mb - 4 * a * c)
                # l = (mb + rad)/(2 * a)
                u = (mb - rad) / (2 * a)
                return np.where(y < d, 0, np.maximum(0, u))

        elif self._name == 'dual':
            # dual moment
            p = self.shape
            q = 1 / p
            self.has_mass = False

            def g(x):
                return 1 - (1 - x)**p

            def g_inv(y):
                return 1 - (1 - y)**q

        elif self._name == 'wtdtvar':
            # weighted tvar, df = p0 <p1, shape = weight on p1
            try:
                self.has_mass = False
                p0, p1 = df
                w = shape
                # print(self._name, p0, p1, w)
                assert p0 < p1
                pt = (1 - p1) / (1 - p0) * (1 - w) + w
                s = np.array([0.,  1-p1, 1-p0, 1.])
                gs = np.array([0.,   pt,   1., 1.])
                g = interp1d(s, gs, kind='linear')
                g_inv = interp1d(gs, s, kind='linear')
            except:
                raise ValueError('Inadmissible parameters to Distortion for wtdtvar'
                                 'pass shape=wt for p1 and df=[p0, p1]')

        elif self._name == 'convex':
            # convex envelope and general interpolation
            self.has_mass = False
            # use shape for number of points in calibrating data set
            self.shape = f'on {len(df):d} points'
            if not (0 in df[col_x].values and 1 in df[col_x].values):
                # painful...always want 0 and 1 there...but don't know what other columns in df
                # logger.debug('df does not contain s=0/1...adding')
                df = df[[col_x, col_y]].copy().reset_index(drop=True)
                df.loc[len(df)] = (0,0)
                df.loc[len(df)] = (1,1)
                df = df.sort_values(col_x)
            if len(df) > 2:
                hull = ConvexHull(df[[col_x, col_y]])
                knots = list(set(hull.simplices.flatten()))
                g = interp1d(df.iloc[knots, df.columns.get_loc(col_x)],
                             df.iloc[knots, df.columns.get_loc(col_y)], kind='linear')
                g_inv = interp1d(df.iloc[knots, df.columns.get_loc(col_y)],
                             df.iloc[knots, df.columns.get_loc(col_x)], kind='linear')
            else:
                df = df.sort_values(col_x)
                g = interp1d(df[col_x], df[col_y], kind='linear')
                g_inv = interp1d(df[col_y], df[col_x], kind='linear')
        else:
            raise ValueError(
                "Incorrect spec passed to Distortion; implemented g types are ph, wang, tvar, "
                "ly (linear yield), lep (layer equivalent pricing) and clin (clipped linear)")

        self.g = g
        self.g_inv = g_inv
        def g_dual(x):
            return 1 - self.g(x)
        self.g_dual = g_dual

    def __str__(self):
        """
        printable version of distortion

        :return:
        """
        if self.display_name != '':
            s = self.display_name
            return s
        elif isinstance(self.shape, str):
            s = f'{self._distortion_names_.get(self._name, self._name)}, {self.shape}'
        else:
            s = f'{self._distortion_names_.get(self._name, self._name)}, {self.shape:.3f}'
        if self.has_mass:
            s += f', {self.r0:.3f}'
        if self._name == 'tt':
            s += f', {self.df:.2f}'
        if self._name == 'wtdtvar':
            s += f', ({self.df[1]:.3f}/{self.df[0]:.3f})'
        return s

    def __repr__(self):
        s = f'{self.name} ({self.shape}'
        if self.has_mass:
            s += f', {self.r0})'
        elif self._name == 'tt':
            s += f', {self.df:.2f})'
        else:
            s += ')'
        return s

    @property
    def name(self):
        return self.display_name if self.display_name != '' else self._name

    @name.setter
    def name(self, value):
        self._name = value

    def plot(self, xs=None, n=101, both=True, ax=None, plot_points=True, scale='linear', c=None, **kwargs):
        """
        quick plot of the distortion

        :param ax:
        :param xs:
        :param n:  length of vector is no xs
        :param both: True: plot g and ginv and add decorations, if False just g and no trimmings
        :param scale: linear as usual or return plots -log(gs)  vs -logs and inverts both scales
        :param kwargs:  passed to plot
        :return:
        """

        assert scale in ['linear', 'return']

        if xs is None:
            xs = np.linspace(0, 1, n)

        y1 = self.g(xs)
        if both:
            y2 = self.g_inv(xs)

        if ax is None:
            ax = plt.gca()

        if scale == 'linear':
            ax.plot(xs, y1, c='C0', label='$g$', **kwargs)
            if both:
                ax.plot(xs, y2, c='C1', label='$g^{-1}$', **kwargs)
            ax.plot(xs, xs, lw=0.5, color='black', alpha=0.5)
        elif scale == 'return':
            ax.plot(xs, y1, c='C0', label='$g$', **kwargs)
            if both:
                ax.plot(xs, y2, c='C1', label='$g^{-1}$', **kwargs)
            ax.set(xscale='log', yscale='log', xlim=[1/2000, 1], ylim=[1/2000, 1])
            ax.plot(xs, xs, lw=0.5, color='black', alpha=0.5)

        if self._name == 'convex' and plot_points:
            if len(self.df) > 50:
                alpha = .35
            elif len(self.df) > 20:
                alpha = 0.6
            else:
                alpha = 1
            if c is None:
                c = 'C2'
            if scale == 'linear':
                ax.scatter(x=self.df[self.col_x], y=self.df[self.col_y], marker='.', s=15, color=c, alpha=alpha)
            elif scale == 'return':
                ax.scatter(x=1/self.df[self.col_x], y=1/self.df[self.col_y], marker='.', s=15, color=c, alpha=alpha)

        ax.grid(linewidth='0.25')

        ax.set(title=fill(str(self), 20), aspect='equal')

        return ax

    @classmethod
    def test(cls, r0=0.035, df=[0.0, .9]):
        """
        tester: make some nice plots

        :return:
        """

        f0, axs0 = plt.subplots(2, 11, figsize=(22, 4), constrained_layout=True, sharex=True, sharey=True)
        f1, axs1 = plt.subplots(2, 11, figsize=(22, 4), constrained_layout=True, sharex=True, sharey=True)
        axiter0 = iter(axs0.flat)
        axiter1 = iter(axs1.flat)

        xs = np.linspace(0, 1, 1001)

        # zip stops at the shorter of the vectors, so this does not include convex (must be listed last)
        # added df for the t; everyone else can ignore it
        # rank by order on large lsoses...
        for axiter, scale in zip([axiter0, axiter1], ['linear', 'return']):
            for name, shape in zip(cls._available_distortions_, cls._eg_param_1_):
                dist = Distortion(name, shape, r0, df=df)
                dist.plot(xs, ax=next(axiter), scale=scale)

            dist = Distortion.convex_example('bond')
            dist.plot(xs, ax=next(axiter), scale=scale)

            # order will look better like this
            for name, shape in zip(cls._available_distortions_, cls._eg_param_2_):
                dist = Distortion(name, shape, r0, df=df)
                dist.plot(xs, ax=next(axiter), scale=scale)

            dist = Distortion.convex_example('cat')
            dist.plot(xs, ax=next(axiter), scale=scale)

        # tidy up
        for ax in axiter0:
            f.delaxes(ax)
        for ax in axiter1:
            f.delaxes(ax)

        f0.suptitle('Example Distortion Functions - Linear Scale')
        f1.suptitle('Example Distortion Functions - Return Scale')

    @staticmethod
    def distortions_from_params(params, index, r0=0.025, df=5.5, plot=True, axiter=None, pricing=True, strict=True):
        """
        make set of dist funs and inverses from params, output of port.calibrate_distortions
        params must just have one row for each method and be in the output format of cal_dist

        :param plot:
        :param index:
        :param r0: min rol parameters
        :param params: dataframe such that params[index, :] has a [lep, param] etc.
        pricing=True, strict=True: which distortions to allow
        df for t distribution
        :return:
        """
        temp = params.loc[index, :]
        dists = {}
        for dn in Distortion.available_distortions(pricing=pricing, strict=strict):
            param = float(temp.loc[dn, 'param'])
            dists[dn] = Distortion(name=dn, shape=param, r0=r0, df=df)

        if plot:
            axiter = axiter_factory(axiter, len(dists))
            # f, axs = plt.subplots(2, 3, figsize=(8, 6))
            # it = iter(axs.flatten())
            for dn in Distortion.available_distortions(pricing=pricing, strict=strict):
                dists[dn].plot(ax=next(axiter))
            try:
                axiter.tidy()
                plt.tight_layout()
            except:
                # fails if axiter is just an iteration of axis elements
                # assume then that constrained_layout =True so no tight layout
                pass

        return dists  # [g_lep, g_ph, g_wang, g_ly, g_clin]

    @staticmethod
    def convex_example(source='bond'):
        """
        example convex distortion using data from https://www.bis.org/publ/qtrpdf/r_qt0312e.pdf

        :param source: bond gives a bond yield curve example, cat gives cat bond / cat reinsurance pricing based example
        :return:
        """

        if source == 'bond':
            yield_curve = '''
            AAAA    0.000000  0.000000
            AAA     0.000018  0.006386
            AA      0.000144  0.007122
            A       0.000278  0.010291
            BBB     0.002012  0.017089
            BB      0.012674  0.036455
            B       0.040052  0.069181
            Z       1.000000  1.000000'''

            df = pd.read_fwf(StringIO(yield_curve))
            df.columns = ['Rating', 'EL', 'Yield']
            return Distortion('convex', 'Yield Curve', df=df, col_x='EL', col_y='Yield')

        elif source.lower() == 'cat':
            cat_bond = '''EL,ROL
            0.116196,0.32613
            0.088113,0.2452
            0.074811,0.22769
            0.056385,0.17131
            0.046923,0.15326
            0.032961,0.12222
            0.02807,0.11037
            0.024205,0.1022
            0.011564,0.07284
            0.005813,0.06004
            0,0
            1,1'''
            df = pd.read_csv(StringIO(cat_bond))
            return Distortion('convex', 'Cat Bond', df=df, col_x='EL', col_y='ROL')

        else:
            raise ValueError(f'Inadmissible value {source} passed to convex_example, expected yield or cat')

    @staticmethod
    def bagged_distortion(data, proportion, samples, display_name="", random_state=None):
        """
        make a distortion by bootstrap aggregation (Bagging) resampling, taking the convex envelope,
        and averaging from data

        Each sample uses proportion of the data

        data has columns just two columns: EL and Spread

        :param data:
        :param proportion: proportion of data for each sample
        :param samples: number of resamples
        :param display_name: display_name of created distortion
        :param random_state: for pd.sample....ensures reproducibility
        :return:
        """

        df = pd.DataFrame(index=np.linspace(0,1,10001), dtype=np.float)

        for i in range(samples):
            rebit = data.sample(frac=proportion, replace=False, random_state=random_state)
            rebit.loc[-1] = [0, 0]
            rebit.loc[max(rebit.index)+1] = [1, 1]
            d = Distortion('convex', 0, df=rebit, col_x='EL', col_y='Spread')
            df[i] = d.g(df.index)

        df['avg'] = df.mean(axis=1)
        df2 =df['avg'].copy()
        df2.index.name = 's'
        df2 = df2.reset_index(drop=False)

        d = Distortion('convex', 0, df=df2, col_x='s', col_y='avg', display_name=display_name)

        return d

    @staticmethod
    def average_distortion(data, display_name, n=201, el_col='EL', spread_col='Spread'):
        """
        create average distortion from (s, g(s)) pairs. Each point defines a wtdTVaR with
        p=s and p=1 points

        :param data:
        :param display_name:
        :param n: number of s values (between 0 and max(EL), 1 is added
        :param el_col:   column containing EL
        :param spread_col: column containing Spread
        :return:
        """

        els = data[el_col]
        spreads = data[spread_col]
        max_el = els.max()
        s = np.hstack((np.linspace(0, max_el, n), 1))
        ans = np.zeros((len(s), len(data)))
        for i, el, spread in zip(range(len(data)), els, spreads):
            p = 1 - el
            w = (spread - el) / (1 - el)
            d = Distortion('wtdtvar', w, df=[0,p])
            ans[:, i] = d.g(s)

        df = pd.DataFrame({'s': s, 'gs': np.mean(ans, 1)})
        dout = Distortion('convex', None, df=df, col_x='s', col_y='gs', display_name=display_name)
        return dout

    @staticmethod
    def wtd_tvar(ps, wts, display_name='', details=False):
        """
        a careful version of wtd tvar with knots at ps and wts

        :param ps:
        :param wts:
        :param display_name:
        :param details:
        :return:
        """

        # evaluate at 0, 1 and all the knot points
        ps0 = np.array(ps)
        s = np.array(sorted(set((0.,1.)).union(1-ps0)))
        s = s.reshape(len(s), 1)

        wts = np.array(wts).reshape(len(wts), 1)
        if np.sum(wts) != 1:
            wts = wts / np.sum(wts)
        ps = np.array(ps).reshape(1, len(ps))

        gs = np.where(ps == 1, 1, np.minimum(s / (1 - ps), 1)) @ wts

        d = Distortion.s_gs_distortion(s, gs, display_name)
        if details:
            return d, s, gs
        else:
            return d

    @staticmethod
    def s_gs_distortion(s, gs, display_name=''):
        """
        make a convex envelope distortion from {s, g(s)} points

        :param s: iterable (can be converted into numpy.array
        :param gs:
        :param display_name:
        :return:
        """
        s = np.array(s)
        gs = np.array(gs)
        return Distortion('convex', None, df=pd.DataFrame({'s': s.flat, 'gs': gs.flat}),
                          col_x='s', col_y='gs', display_name=display_name)

