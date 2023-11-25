"""Preprocessing tools based on orthogonal polynomial features."""

# import statements
import numpy as np

# sklearn imports
from ..base import BaseEstimator, TransformerMixin, _fit_context
from ..utils._multiindexset import MultiIndexSet
from ..utils._orthogonal_polynomial import (  # noqa: F401
    Hermite,
    Jacobi,
    Laguerre,
    Legendre,
)
from ..utils._param_validation import Integral, Interval, Iterable, StrOptions
from ..utils.validation import (
    _check_feature_names_in,
    check_array,
    check_is_fitted,
)


class OrthogonalPolynomialFeatures(BaseEstimator, TransformerMixin):
    r"""Generate orthogonal polynomial and interaction features.

    Generate a new feature matrix consisting of combinations of orthogonal
    polynomials of the features. This is an extension of
    :class:`~sklearn.preprocessing.PolynomialFeatures`, where the monomials are
    replaced by a (combination of) orthogonal polynomials. For example, if
    :math:`p_j` and :math:`q_j` are orthogonal polynomials of degree :math:`j`,
    and for input features :math:`a` and :math:`b`, the degree-2 orthogonal
    polynomial features are

    .. math::
        p_0(a)q_0(b)\quad
        p_1(a)q_0(b)\quad
        p_2(a)q_0(b)\quad
        p_0(a)q_1(b)\quad
        p_1(a)q_1(b)\quad
        p_0(a)q_2(b)

    Read more in the
    :ref:`User Guide <generating_orthogonal_polynomial_features>`.

    Parameters
    ----------
    degree : int, default=2
        The maximum degree of the orthogonal polynomial features.

    polynomial : str or tuple \
        (poly_1, poly_2, ...), default='Legendre'
        If a single orthogonal polynomial name is given, the same polynomial
        type is used for all features. If a tuple (`poly_1`, `poly_2`, ...)` is
        passed, then `poly_1` is the orthogonal polynomial for the first
        feature, `poly_2` is the orthogonal polynomial for the second feature
        and so on. Note that when a tuple is passed, its length must be
        consistent with the the number of input features and the number of
        columns in `multiindices` (when the latter is provided). The default is
        `'Legendre'`.

    truncation : {'full_tensor', 'total_degree', 'hyperbolic_cross', \
        'Zaremba_cross'}, default='total_degree'
        The truncation rule that should be used to determine the shape of the
        multiindex set that governs which combinations of input features to
        retain in the output features. The default is `'total_degree'`.

    weights : array-like, default=None
        Optional weights that can be used to select preferential directions in
        the multiindex set that governs which combinations of input features to
        retain in the output features. A larger value for the weight of a
        certain feature indicates that a higher-degree polynomial will be used
        in the output features. The weights must be all positive. When `weights
        = None`, an unweighted multiindex set will be used. The default is
        `None`.

    indices : array-like of shape (n_output_features_, n_features_in_), \
        dtype=np.int64, default=None
        The combination of `degree`, `truncation` and `weights` provides a
        flexible way to define various multiindex set shapes that govern which
        combinations of input features to retain in the output features. To
        allow for even more fine-grained control, this optional argument allows
        to specify an arbitrary set of multiindices that will be used instead.
        When this argument is provided, it supersedes the values in `degree`,
        `truncation` and `weights`. If `multiindices = None`, then the
        multiindex set shape given in `truncation` will be used. The default is
        `None`.

    Attributes
    ----------
    n_features_in_ : int
        Number of features seen during :term:`fit`.

    feature_names_in_ : ndarray of shape (n_features_in_,)
        Names of features seen during :term:`fit`. Defined only when `X`
        has feature names that are all strings.

    n_output_features_ : int
        The total number of orthogonal polynomial output features.

    multiindices_ : array-like of shape (n_output_features_, n_features_in_)
        An array with the combinations of input features that will be used to
        compose the output features. Every row in this array contains a single
        multiindex.

    maximum_degrees_ : array-like of shape (n_features_in_,)
        The maximum degree of the orthogonal polynomial output features for
        each input feature.

    See Also
    --------
    :class:`~sklearn.preprocessing.PolynomialFeatures`: Transformer that uses a
        (non-orthogonal) monomial basis instead of an orthogonal polynomial
        basis.
    :class:`~sklearn.polynomial_chaos.PolynomialChaosRegressor`: Estimator that
        transforms a given set of input features into orthogonal polynomial
        features and fits the coefficients against a given data set.

    Notes
    -----
    Be aware that the number of output features scales exponentially in the
    number of input features and the `degree`. High degrees can cause
    overfitting, see
    :ref:`sphx_glr_auto_examples_polynomial_chaos_plot_simple_1d.py`.

    Examples
    --------
    >>> import numpy as np
    >>> from sklearn.preprocessing import OrthogonalPolynomialFeatures
    >>> X = np.linspace(0, 1, num=6).reshape(3, 2)
    >>> X
    array([[0. , 0.2],
           [0.4, 0.6],
           [0.8, 1. ]])
    >>> poly = OrthogonalPolynomialFeatures()
    >>> poly.fit_transform(X)
    array([[ 1.  ,  0.  , -0.5 ,  0.2 ,  0.  , -0.44],
           [ 1.  ,  0.4 , -0.26,  0.6 ,  0.24,  0.04],
           [ 1.  ,  0.8 ,  0.46,  1.  ,  0.8 ,  1.  ]])
    """

    _parameter_constraints: dict = {
        "degree": [Interval(Integral, 0, None, closed="left")],
        "polynomial": [str, "array-like"],
        "truncation": [
            StrOptions(
                {
                    "full_tensor",
                    "total_degree",
                    "hyperbolic_cross",
                    "Zaremba_cross",
                }
            )
        ],
        "weights": ["array-like", None],
        "multiindices": ["array-like", Iterable, None],
    }

    def __init__(
        self,
        degree=2,
        polynomial="Legendre",
        *,
        truncation="total_degree",
        weights=None,
        multiindices=None,
    ):
        self.degree = degree
        self.polynomial = polynomial
        self.truncation = truncation
        self.weights = weights
        self.multiindices = multiindices

    def get_feature_names_out(self, input_features=None):
        """Get output feature names for transformation.

        Parameters
        ----------
        input_features : array-like of str or None, default=None
            Input features.

            - If `input_features` is `None`, then `feature_names_in_` is
              used as feature names in. If `feature_names_in_` is not defined,
              then the following input feature names are generated:
              `["x0", "x1", ..., "x(n_features_in_ - 1)"]`.
            - If `input_features` is an array-like, then `input_features` must
              match `feature_names_in_` if `feature_names_in_` is defined.

        Returns
        -------
        feature_names_out : `ndarray` of `str` objects
            Transformed feature names.
        """
        check_is_fitted(self)
        input_features = _check_feature_names_in(self, input_features)
        feature_names = list()
        for multiindex in self.multiindices_:
            feature_names.append(
                "*".join(
                    f"{polynomial.__class__.__name__}{index}({input_feature})"
                    for polynomial, index, input_feature in zip(
                        self.polynomials_, multiindex, input_features
                    )
                )
            )
        return np.asarray(feature_names, dtype=object)

    @_fit_context(prefer_skip_nested_validation=True)
    def fit(self, X, y=None):
        """
        Compute the desired combinations of output features.

        Parameters
        ----------
        X : array-like of shape (`n_samples`, `n_features`)
            The data.

        y : Ignored
            Not used, present here for API consistency by convention.

        Returns
        -------
        self : object
            Fitted transformer.
        """

        # check input data
        _, n_features = self._validate_data(X).shape

        # check polynomial
        polynomials = self.polynomial
        if isinstance(polynomials, str):
            polynomials = [polynomials] * n_features
        polynomials = list(polynomials)
        if not len(polynomials) == n_features:
            raise ValueError(
                "the number of polynomials does not match the number of "
                f"input features, got {len(polynomials)} but "
                f"expected {n_features}"
            )
        self.polynomials_ = list()
        for j, polynomial in enumerate(polynomials):
            try:
                terms = polynomial.split("_")
                poly = eval(f"{terms[0].capitalize()}")
                params = [float(param) for param in terms[1:]]
                self.polynomials_.append(poly() if len(params) == 0 else poly(*params))
            except Exception:
                raise ValueError(
                    f"could not interpret the polynomial at index {j} "
                    f"as a valid polynomial, got '{polynomial}'"
                )

        # generate multiindex set
        if self.multiindices is None:  # no multiindices were provided
            m_type = MultiIndexSet.from_string(self.truncation)
            m = m_type(n_features, self.degree, weights=self.weights)
            self.multiindices_ = np.vstack(list(m.indices()))
        else:  # a set of custom multiindices was provided
            self.multiindices_ = check_array(list(self.multiindices), dtype="int64")

        # get maximum required polynomial degree for each feature
        self.maximum_degrees_ = np.amax(self.multiindices_, axis=0)

        # set number of output features
        self.n_output_features_ = self.multiindices_.shape[0]

        # compute the norms of each orthogonal polynomial
        # NOTE: This is useful for global sensitivity analysis using Polynomial
        # Chaos regression, which requires access to the norms of the
        # orthogonal polynomials in the basis.
        self.norms_ = np.ones(self.n_output_features_)
        for j, index in enumerate(self.multiindices_):
            for dim in range(n_features):
                self.norms_[j] *= self.polynomials_[dim].norm(index[dim])

        # by convention, fit returns self
        return self

    def transform(self, X):
        """Transform data to orthogonal polynomial features.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features_in_)
            The data to transform, one data point on every row.

        Returns
        -------
        X_trans : ndarray of shape (n_samples, n_output_features_)
            The matrix of features, where `n_output_features_` is the number of
            othogonal polynomial features generated from all combinations of
            input features.
        """

        # check if fit has been called
        check_is_fitted(self)
        X = self._validate_data(X, reset=False, accept_sparse=False, ensure_2d=True)
        n_samples, n_features = X.shape

        # compute the 1d polynomial features
        polynomial_features = list()
        for j, polynomial in enumerate(self.polynomials_):
            polynomial_features.append(
                polynomial.vandermonde(X[:, j], self.maximum_degrees_[j])
            )

        # compose output features by multiplying 1d polynomial features
        X_trans = np.ones((n_samples, self.n_output_features_))
        for j, index in enumerate(self.multiindices_):
            for dim in range(n_features):
                X_trans[:, j] *= polynomial_features[dim][:, index[dim]]

        return X_trans
