import ctypes
from typing import List, Optional, Tuple

import numpy as np
import numpy.typing as npt
from numpy.ctypeslib import ndpointer

from .compile import compile_model
from .util import validate_readable

FloatArray = npt.NDArray[np.float64]
double_array = ndpointer(dtype=ctypes.c_double, flags=("C_CONTIGUOUS"))


class StanModel:
    """
    A StanModel instance encapsulates a Stan model instantiated with data
    and provides methods to access parameter names, transforms, log
    densities, gradients, and Hessians.

    The constructor method instantiates a Stan model and sets constant
    return values.  The constructor arguments are

    :param model_lib: A path to a compiled shared object.
    :param model_data: Either a JSON string literal or a
         path to a data file in JSON format ending in ``.json``.
    :param seed: A pseudo random number generator seed.
    :param chain_id: A unique identifier for concurrent chains of
        pseudorandom numbers.
    :raises FileNotFoundError or PermissionError: If ``model_lib`` is not readable or
        ``model_data`` is specified and not a path to a readable file.
    :raises RuntimeError: If there is an error instantiating the Stan model.
    """

    def __init__(
        self,
        model_lib: str,
        model_data: Optional[str] = None,
        *,
        seed: int = 1234,
        chain_id: int = 0,
    ) -> None:
        """
        Construct a StanModel object for a Stan model and data given
        constructor arguments.

        :param model_lib: A system path to compiled shared object.
        :param model_data: Either a JSON string literal or a
            system path to a data file in JSON format ending in ``.json``.
        :param seed: A pseudo random number generator seed.
        :param chain_id: A unique identifier for concurrent chains of
            pseudorandom numbers.
        :raises FileNotFoundError or PermissionError: If ``model_lib`` is not readable or
            ``model_data`` is specified and not a path to a readable file.
        :raises RuntimeError: If there is an error instantiating the
            model from C++.
        """
        validate_readable(model_lib)
        if not model_data is None and model_data.endswith('.json'):
            validate_readable(model_data)
        self.lib_path = model_lib
        self.stanlib = ctypes.CDLL(self.lib_path)
        self.data_path = model_data or ""
        self.seed = seed
        self.chain_id = chain_id

        self._construct = self.stanlib.bs_construct
        self._construct.restype = ctypes.c_void_p
        self._construct.argtypes = [ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint]

        self.model_rng = self._construct(
            str.encode(self.data_path), self.seed, self.chain_id
        )

        if not self.model_rng:
            raise RuntimeError("could not construct model RNG")

        self._name = self.stanlib.bs_name
        self._name.restype = ctypes.c_char_p
        self._name.argtypes = [ctypes.c_void_p]

        self._model_info = self.stanlib.bs_model_info
        self._model_info.restype = ctypes.c_char_p
        self._model_info.argtypes = [ctypes.c_void_p]

        self._param_num = self.stanlib.bs_param_num
        self._param_num.restype = ctypes.c_int
        self._param_num.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]

        self._param_unc_num = self.stanlib.bs_param_unc_num
        self._param_unc_num.restype = ctypes.c_int
        self._param_unc_num.argtypes = [ctypes.c_void_p]

        self._param_names = self.stanlib.bs_param_names
        self._param_names.restype = ctypes.c_char_p
        self._param_names.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
        ]

        self._param_unc_names = self.stanlib.bs_param_unc_names
        self._param_unc_names.restype = ctypes.c_char_p
        self._param_unc_names.argtypes = [ctypes.c_void_p]

        self._param_constrain = self.stanlib.bs_param_constrain
        self._param_constrain.restype = ctypes.c_int
        self._param_constrain.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            double_array,
            double_array,
        ]

        self._param_unconstrain = self.stanlib.bs_param_unconstrain
        self._param_unconstrain.restype = ctypes.c_int
        self._param_unconstrain.argtypes = [ctypes.c_void_p, double_array, double_array]

        self._param_unconstrain_json = self.stanlib.bs_param_unconstrain_json
        self._param_unconstrain_json.restype = ctypes.c_int
        self._param_unconstrain_json.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            double_array,
        ]

        self._log_density = self.stanlib.bs_log_density
        self._log_density.restype = ctypes.c_int
        self._log_density.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            double_array,
            ctypes.POINTER(ctypes.c_double),
        ]

        self._log_density_gradient = self.stanlib.bs_log_density_gradient
        self._log_density_gradient.restype = ctypes.c_int
        self._log_density_gradient.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            double_array,
            ctypes.POINTER(ctypes.c_double),
            double_array,
        ]

        self._log_density_hessian = self.stanlib.bs_log_density_hessian
        self._log_density_hessian.restype = ctypes.c_int
        self._log_density_hessian.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            double_array,
            ctypes.POINTER(ctypes.c_double),
            double_array,
            double_array,
        ]

        self._destruct = self.stanlib.bs_destruct
        self._destruct.restype = ctypes.c_int
        self._destruct.argtypes = [ctypes.c_void_p]

    @classmethod
    def from_stan_file(
        cls,
        stan_file: str,
        model_data: Optional[str] = None,
        *,
        stanc_args: List[str] = [],
        make_args: List[str] = [],
        seed: int = 1234,
        chain_id: int = 0,
    ):
        """
        Construct a StanModel instance from a ``.stan`` file, compiling if necessary.

        This is equivalent to calling :func:`bridgestan.compile_model` and then the
        constructor of this class.

        :param stan_file: A path to a Stan model file.
        :param model_data: A path to data in JSON format.
        :param stanc_args: A list of arguments to pass to stanc3.
            For example, ``["--O1"]`` will enable compiler optimization level 1.
        :param make_args: A list of additional arguments to pass to Make.
            For example, ``["STAN_THREADS=True"]`` will enable
            threading for the compiled model. If the same flags are defined
            in ``make/local``, the versions passed here will take precedent.
        :param seed: A pseudo random number generator seed.
        :param chain_id: A unique identifier for concurrent chains of
            pseudorandom numbers.
        :raises FileNotFoundError or PermissionError: If `stan_file` does not exist
            or is not readable.
        :raises ValueError: If BridgeStan cannot be located.
        :raises RuntimeError: If compilation fails.
        """
        result = compile_model(stan_file, stanc_args=stanc_args, make_args=make_args)
        return cls(str(result), model_data, seed=seed, chain_id=chain_id)

    def __del__(self) -> None:
        """
        Destroy the Stan model and free memory.
        """
        if hasattr(self, "model_rng") and hasattr(self, "_destruct"):
            self._destruct(self.model_rng)

    def __repr__(self) -> str:
        data = f"{self.data_path!r}, " if self.data_path else ""
        return f"StanModel({self.lib_path!r}, {data}seed={self.seed}, chain_id={self.chain_id})"

    def name(self) -> str:
        """
        Return the name of the Stan model.

        :return: The name of Stan model.
        """
        return self._name(self.model_rng).decode("utf-8")

    def model_info(self) -> str:
        """
        Return compilation information about the model. For example,
        this includes the current Stan version and important
        compiler settings.

        :return: Information about the compiled Stan model.
        """
        return self._model_info(self.model_rng).decode("utf-8")

    def param_num(self, *, include_tp: bool = False, include_gq: bool = False) -> int:
        """
        Return the number of parameters, including transformed
        parameters and/or generated quantities as indicated.

        :param include_tp: `True` to include the transformed parameters.
        :param include_gq: `True` to include the generated quantities.
        :return: The number of parameters.
        """
        return self._param_num(self.model_rng, int(include_tp), int(include_gq))

    def param_unc_num(self) -> int:
        """
        Return the number of unconstrained parameters.

        :return: The number of unconstrained parameters.
        """
        return self._param_unc_num(self.model_rng)

    def param_names(
        self, *, include_tp: bool = False, include_gq: bool = False
    ) -> List[str]:
        """
        Return the indexed names of the parameters, including transformed
        parameters and/or generated quantities as indicated.  For
        containers, indexes are separated by periods (`.`).
        For example, the scalar `a` has
        indexed name `a`, the vector entry `a[1]` has indexed name `a.1`
        and the matrix entry `a[2, 3]` has indexed name `a.2.3`.
        Parameter order of the output is column major and more
        generally last-index major for containers.

        :param include_tp: `True` to include transformed parameters.
        :param include_gq: `True` to include generated quantities.
        :return: The indexed names of the parameters.
        """
        return (
            self._param_names(self.model_rng, int(include_tp), int(include_gq))
            .decode("utf-8")
            .split(",")
        )

    def param_unc_names(self) -> List[str]:
        """
        Return the indexed names of the unconstrained parameters.
        For example, a scalar unconstrained parameter `b` has indexed
        name `b` and a vector entry `b[3]` has indexed name `b.3`.

        :return: The indexed names of the unconstrained parameters.
        """
        return self._param_unc_names(self.model_rng).decode("utf-8").split(",")

    def param_constrain(
        self,
        theta_unc: FloatArray,
        *,
        include_tp: bool = False,
        include_gq: bool = False,
        out: Optional[FloatArray] = None,
    ) -> FloatArray:
        """
        Return the constrained parameters derived from the specified
        unconstrained parameters as an array, optionally including the
        transformed parameters and/or generated quantitities as specified.
        Including generated quantities uses the PRNG and may update its state.
        Setting `out` avoids allocation of a new array for the return value.

        :param theta_unc: Unconstrained parameter array.
        :param include_tp: `True` to include transformed parameters.
        :param include_gq: `True` to include generated quantities.
        :param out: A location into which the result is stored.  If
            provided, it must have shape `(D, )`, where `D` is the number of
            constrained parameters.  If not provided or `None`, a freshly
            allocated array is returned.
        :return: The constrained parameter array.
        :raises ValueError: If `out` is specified and is not the same
            shape as the return.
        :raises RuntimeError: If the C++ Stan model throws an exception.
        """
        dims = self.param_num(include_tp=include_tp, include_gq=include_gq)
        if out is None:
            out = np.zeros(dims)
        elif out.size != dims:
            raise ValueError(
                "Error: out must be same size as number of constrained parameters"
            )
        rc = self._param_constrain(
            self.model_rng, int(include_tp), int(include_gq), theta_unc, out
        )
        if rc:
            raise RuntimeError(
                "param_constrain failed on C++ side; see stderr for messages"
            )
        return out

    def param_unconstrain(
        self, theta: FloatArray, *, out: Optional[FloatArray] = None
    ) -> FloatArray:
        """
        Return the unconstrained parameters derived from the specified
        constrained parameters.  Setting `out` avoids allocation of a
        new array for the return value.

        :param theta: Constrained parameter array.
        :param out: A location into which the result is stored.  If
            provided, it must have shape `(D, )`, where `D` is the number of
            unconstrained parameters.  If not provided or `None`, a freshly
            allocated array is returned.
        :raises ValueError: If `out` is specified and is not the same
            shape as the return.
        :raises RuntimeError: If the C++ Stan model throws an exception.
        """
        dims = self.param_unc_num()
        if out is None:
            out = np.zeros(shape=dims)
        elif out.size != dims:
            raise ValueError(
                f"out size = {out.size} != unconstrained params size = {dims}"
            )
        rc = self._param_unconstrain(self.model_rng, theta, out)
        if rc:
            raise RuntimeError(
                "param_unconstrain failed on C++ side; see stderr for messages"
            )
        return out

    def param_unconstrain_json(
        self, theta_json: str, *, out: Optional[FloatArray] = None
    ) -> FloatArray:
        """
        Return an array of the unconstrained parameters derived from the
        specified JSON formatted data.  See the *CmdStan Reference
        Manual* for the schema definition used.

        :param theta_json: The JSON encoded constrained parameters.
        :param out: A location into which the result is stored.  If
            provided, it must have shape `(D, )`, where `D` is the number of
            unconstrained parameters.  If not provided or `None`, a freshly
            allocated array is returned.
        :return: The unconstrained parameter array.
        :raises ValueError: If `out` is specified and is not the same
            shape as the return value.
        :raises RuntimeError: If the C++ Stan model throws an exception.
        """
        dims = self.param_unc_num()
        if out is None:
            out = np.zeros(shape=dims)
        elif out.size != dims:
            raise ValueError(
                f"out size = {out.size} != unconstrained params size = {dims}"
            )
        chars = theta_json.encode("UTF-8")
        rc = self._param_unconstrain_json(self.model_rng, chars, out)
        if rc:
            raise RuntimeError(
                "param_unconstrain_json failed on C++ side; see stderr for messages"
            )
        return out

    def log_density(
        self,
        theta_unc: FloatArray,
        *,
        propto: bool = True,
        jacobian: bool = True,
    ) -> float:
        """
        Return the log density of the specified unconstrained
        parameters, dropping constant terms that do not depend on the
        parameters if `propto` is `True` and including change of
        variables terms for constrained parameters if `jacobian` is `True`.

        :param theta_unc: Unconstrained parameter array.
        :param propto: `True` if constant terms should be dropped from the log density.
        :param jacobian: `True` if change-of-variables terms for
            constrained parameters should be included in the log density.
        :return: The log density.
        :raises RuntimeError: If the C++ Stan model throws an exception.
        """
        lp = ctypes.pointer(ctypes.c_double())
        rc = self._log_density(
            self.model_rng, int(propto), int(jacobian), theta_unc, lp
        )
        if rc:
            raise RuntimeError(
                "C++ exception in log_density(); see stderr for messages"
            )
        return lp.contents.value

    def log_density_gradient(
        self,
        theta_unc: FloatArray,
        *,
        propto: bool = True,
        jacobian: bool = True,
        out: Optional[FloatArray] = None,
    ) -> Tuple[float, FloatArray]:
        """
        Return a tuple of the log density and gradient of the specified
        unconstrained parameters, dropping constant terms that do not depend
        on the parameters if `propto` is `True` and including change of
        variables terms for constrained parameters if `jacobian`
        is `True`.

        :param theta_unc: Unconstrained parameter array.
        :param propto: `True` if constant terms should be dropped from the log density.
        :param jacobian: `True` if change-of-variables terms for
            constrained parameters should be included in the log density.
        :param out: A location into which the gradient is stored.  If
            provided, it must have shape `(D, )` where `D` is the number
            of parameters.  If not provided, a freshly allocated array
            is returned.
        :return: A tuple consisting of log density and gradient.
        :raises ValueError: If `out` is specified and is not the same
            shape as the gradient.
        :raises RuntimeError: If the C++ Stan model throws an exception.
        """
        dims = self.param_unc_num()
        if out is None:
            out = np.zeros(shape=dims)
        elif out.size != dims:
            raise ValueError(f"out size = {out.size} != params size = {dims}")
        lp = ctypes.pointer(ctypes.c_double())
        rc = self._log_density_gradient(
            self.model_rng, int(propto), int(jacobian), theta_unc, lp, out
        )
        if rc:
            raise RuntimeError(
                "C++ exception in log_density_gradient(); see stderr for messages"
            )
        return lp.contents.value, out

    def log_density_hessian(
        self,
        theta_unc: FloatArray,
        *,
        propto: bool = True,
        jacobian: bool = True,
        out_grad: Optional[FloatArray] = None,
        out_hess: Optional[FloatArray] = None,
    ) -> Tuple[float, FloatArray, FloatArray]:
        """
        Return a tuple of the log density, gradient, and Hessian of the
        specified unconstrained parameters, dropping constant terms that do
        not depend on the parameters if `propto` is `True` and including
        change of variables terms for constrained parameters if
        `jacobian` is `True`.

        :param theta_unc: Unconstrained parameter array.
        :param propto: `True` if constant terms should be dropped from the log density.
        :param jacobian: `True` if change-of-variables terms for
            constrained parameters should be included in the log density.
        :param out_grad: A location into which the gradient is stored.  If
            provided, it must have shape `(D, )` where `D` is the number
            of parameters.  If not provided, a freshly allocated array
            is returned.
        :param out_hess: A location into which the Hessian is stored. If
            provided, it must have shape `(D, D)`, where `D` is the
            number of parameters.  If not provided, a freshly allocated
            array is returned.
        :return: A tuple consisting of the log density, gradient, and Hessian.
        :raises ValueError: If `out_grad` is specified and is not the
            same shape as the gradient or if `out_hess` is specified and it
            is not the same shape as the Hessian.
        :raises RuntimeError: If the C++ Stan model throws an exception.
        """
        dims = self.param_unc_num()
        if out_grad is None:
            out_grad = np.zeros(shape=dims)
        elif out_grad.shape != (dims,):
            raise ValueError(f"out_grad size = {out_grad.size} != params size = {dims}")
        hess_size = dims * dims
        if out_hess is None:
            out_hess = np.zeros(shape=hess_size)
        elif out_hess.shape != (dims, dims):
            raise ValueError(
                f"out_hess size = {out_hess.size} != params size^2 = {hess_size}"
            )
        lp = ctypes.pointer(ctypes.c_double())
        rc = self._log_density_hessian(
            self.model_rng,
            int(propto),
            int(jacobian),
            theta_unc,
            lp,
            out_grad,
            out_hess,
        )
        if rc:
            raise RuntimeError(
                "C++ exception in log_density_hessian(); see stderr for messages"
            )
        out_hess = out_hess.reshape(dims, dims)
        return lp.contents.value, out_grad, out_hess
