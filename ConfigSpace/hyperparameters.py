from abc import ABCMeta, abstractmethod
import warnings

import numpy as np
import six


class Hyperparameter(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, name):
        if not isinstance(name, six.string_types):
            raise TypeError(
                "The name of a hyperparameter must be an instance of"
                " %s, but is %s." % (str(six.string_types), type(name)))
        self.name = name

    # http://stackoverflow.com/a/25176504/4636294
    def __eq__(self, other):
        """Override the default Equals behavior"""
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return NotImplemented

    def __ne__(self, other):
        """Define a non-equality test"""
        if isinstance(other, self.__class__):
            return not self.__eq__(other)
        return NotImplemented

    def __hash__(self):
        """Override the default hash behavior (that returns the id or the object)"""
        return hash(tuple(sorted(self.__dict__.items())))

    @abstractmethod
    def __repr__(self):
        raise NotImplementedError()

    @abstractmethod
    def is_legal(self, value):
        raise NotImplementedError()

    def sample(self, rs):
        vector = self._sample(rs)
        return self._transform(vector)

    @abstractmethod
    def _sample(self, rs, size):
        raise NotImplementedError()

    @abstractmethod
    def _transform(self, vector):
        raise NotImplementedError()

    @abstractmethod
    def _inverse_transform(self, vector):
        raise NotImplementedError()

    @abstractmethod
    def has_neighbors(self):
        raise NotImplementedError()

    @abstractmethod
    def get_neighbors(self, value, rs, number, transform=False):
        raise NotImplementedError()

    @abstractmethod
    def get_num_neighbors(self):
        raise NotImplementedError()


class Constant(Hyperparameter):
    def __init__(self, name, value):
        super(Constant, self).__init__(name)
        allowed_types = []
        allowed_types.extend(six.integer_types)
        allowed_types.append(float)
        allowed_types.extend(six.string_types)
        allowed_types.append(six.text_type)
        allowed_types = tuple(allowed_types)

        if not isinstance(value, allowed_types) or \
                isinstance(value, bool):
            raise TypeError("Constant value is of type %s, but only the "
                            "following types are allowed: %s" %
                            (type(value), allowed_types))

        self.value = value
        self.default = value

    def __repr__(self):
        repr_str = ["%s" % self.name,
                    "Type: Constant",
                    "Value: %s" % self.value]
        return ", ".join(repr_str)

    def is_legal(self, value):
        return value == self.value

    def _sample(self, rs, size=None):
        return 0 if size == 1 else np.zeros((size,))

    def _transform(self, vector):
        if not np.isfinite(vector):
            return None
        return self.value

    def _inverse_transform(self, vector):
        if vector != self.value:
            return np.NaN
        return 0

    def has_neighbors(self):
        return False

    def get_num_neighbors(self):
        return 0

    def get_neighbors(self, value, rs, number, transform=False):
        return []


class UnParametrizedHyperparameter(Constant):
    pass


class NumericalHyperparameter(Hyperparameter):
    def __init__(self, name, default):
        super(NumericalHyperparameter, self).__init__(name)
        self.default = default

    def has_neighbors(self):
        return True

    def get_num_neighbors(self):
        return np.inf

class FloatHyperparameter(NumericalHyperparameter):
    def __init__(self, name, default):
        super(FloatHyperparameter, self).__init__(name, default)

    def is_legal(self, value):
        return isinstance(value, float) or isinstance(value, int)

    def check_default(self, default):
        return np.round(float(default), 10)


class IntegerHyperparameter(NumericalHyperparameter):
    def __init__(self, name, default):
        super(IntegerHyperparameter, self).__init__(name, default)

    def is_legal(self, value):
        return isinstance(value, int)

    def check_int(self, parameter, name):
        if abs(int(parameter) - parameter) > 0.00000001 and \
                        type(parameter) is not int:
            raise ValueError("For the Integer parameter %s, the value must be "
                             "an Integer, too. Right now it is a %s with value"
                             " %s." % (name, type(parameter), str(parameter)))
        return int(parameter)

    def check_default(self, default):
        return int(np.round(default, 0))


class UniformMixin(object):
    def is_legal(self, value):
        if not super(UniformMixin, self).is_legal(value):
            return False
        # Strange numerical issues!
        elif self.upper >= value >= (self.lower - 0.0000000001):
            return True
        else:
            return False

    def check_default(self, default):
        if default is None:
            if self.log:
                default = np.exp((np.log(self.lower) + np.log(self.upper)) / 2.)
            else:
                default = (self.lower + self.upper) / 2.
        default = super(UniformMixin, self).check_default(default)
        if self.is_legal(default):
            return default
        else:
            raise ValueError("Illegal default value %s" % str(default))


class NormalMixin(object):
    def check_default(self, default):
        if default is None:
            return self.mu
        elif self.is_legal(default):
            return default
        else:
            raise ValueError("Illegal default value %s" % str(default))


class UniformFloatHyperparameter(UniformMixin, FloatHyperparameter):
    def __init__(self, name, lower, upper, default=None, q=None, log=False):
        self.lower = float(lower)
        self.upper = float(upper)
        self.q = float(q) if q is not None else None
        self.log = bool(log)

        if self.lower >= self.upper:
            raise ValueError("Upper bound %f must be larger than lower bound "
                             "%f for hyperparameter %s" %
                             (self.lower, self.upper, name))
        elif log and self.lower <= 0:
            raise ValueError("Negative lower bound (%f) for log-scale "
                             "hyperparameter %s is forbidden." %
                             (self.lower, name))

        super(UniformFloatHyperparameter, self). \
            __init__(name, self.check_default(default))

        if self.log:
            if self.q is not None:
                lower = self.lower - (np.float64(self.q) / 2. - 0.0001)
                upper = self.upper + (np.float64(self.q) / 2. - 0.0001)
            else:
                lower = self.lower
                upper = self.upper
            self._lower = np.log(lower)
            self._upper = np.log(upper)
        else:
            if self.q is not None:
                self._lower = self.lower - (self.q / 2. - 0.0001)
                self._upper = self.upper + (self.q / 2. - 0.0001)
            else:
                self._lower = self.lower
                self._upper = self.upper

    def __repr__(self):
        repr_str = six.StringIO()
        repr_str.write("%s, Type: UniformFloat, Range: [%s, %s], Default: %s" %
                       (self.name, str(self.lower), str(self.upper),
                        str(self.default)))
        if self.log:
            repr_str.write(", on log-scale")
        if self.q is not None:
            repr_str.write(", Q: %s" % str(self.q))
        repr_str.seek(0)
        return repr_str.getvalue()

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return all([self.name == other.name,
                        abs(self.lower - other.lower) < 0.00000001,
                        abs(self.upper - other.upper) < 0.00000001,
                        self.log == other.log,
                        self.q is None and other.q is None or
                        self.q is not None and other.q is not None and
                        abs(self.q - other.q) < 0.00000001])
        else:
            return False

    def to_integer(self):
        # TODO check if conversion makes sense at all (at least two integer
        # values possible!)
        return UniformIntegerHyperparameter(self.name, self.lower,
                                            self.upper,
                                            int(np.round(self.default)), self.q,
                                            self.log)

    def _sample(self, rs, size=None):
        return rs.uniform(size=size)

    def _transform(self, vector):
        if np.isnan(vector):
            return None
        vector *= (self._upper - self._lower)
        vector += self._lower
        if self.log:
            vector = np.exp(vector)
        if self.q is not None:
            vector = int(np.round(vector / self.q, 0)) * self.q
        return vector

    def _inverse_transform(self, vector):
        if vector is None:
            return np.NaN
        if self.log:
            vector = np.log(vector)
        return (vector - self._lower) / (self._upper - self._lower)

    def get_neighbors(self, value, rs, number=4, transform=False):
        neighbors = []
        while len(neighbors) < number:
            neighbor = rs.normal(value, 0.2)
            if neighbor < 0 or neighbor > 1:
                continue
            if transform:
                neighbors.append(self._transform(neighbor))
            else:
                neighbors.append(neighbor)
        return neighbors


class NormalFloatHyperparameter(NormalMixin, FloatHyperparameter):
    def __init__(self, name, mu, sigma, default=None, q=None, log=False):
        self.mu = float(mu)
        self.sigma = float(sigma)
        self.q = float(q) if q is not None else None
        self.log = bool(log)
        super(NormalFloatHyperparameter, self). \
            __init__(name, self.check_default(default))

    def __repr__(self):
        repr_str = six.StringIO()
        repr_str.write("%s, Type: NormalFloat, Mu: %s Sigma: %s, Default: %s" %
                       (self.name, str(self.mu), str(self.sigma),
                        str(self.default)))
        if self.log:
            repr_str.write(", on log-scale")
        if self.q is not None:
            repr_str.write(", Q: %s" % str(self.q))
        repr_str.seek(0)
        return repr_str.getvalue()

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return all([self.name == other.name,
                        abs(self.mu - other.mu) < 0.00000001,
                        abs(self.sigma - other.sigma) < 0.00000001,
                        self.log == other.log,
                        self.q is None and other.q is None or
                        self.q is not None and other.q is not None and
                        abs(self.q - other.q) < 0.00000001])
        else:
            return False

    def to_uniform(self, z=3):
        return UniformFloatHyperparameter(self.name,
                                          self.mu - (z * self.sigma),
                                          self.mu + (z * self.sigma),
                                          default=int(
                                              np.round(self.default, 0)),
                                          q=self.q, log=self.log)

    def to_integer(self):
        return NormalIntegerHyperparameter(self.name, self.mu, self.sigma,
                                           default=int(
                                               np.round(self.default, 0)),
                                           q=self.q, log=self.log)

    def is_legal(self, value):
        if isinstance(value, (float, int)):
            return True
        else:
            return False

    def _sample(self, rs, size=None):
        mu = self.mu
        sigma = self.sigma
        return rs.normal(mu, sigma, size=size)

    def _transform(self, vector):
        if np.isnan(vector):
            return None
        if self.log:
            vector = np.exp(vector)
        if self.q is not None:
            vector = int(np.round(vector / self.q, 0)) * self.q
        return vector

    def _inverse_transform(self, vector):
        if vector is None:
            return np.NaN

        if self.log:
            vector = np.log(vector)
        return vector

    def get_neighbors(self, value, rs, number=4):
        neighbors = []
        for i in range(number):
            neighbors.append(rs.normal(value, self.sigma))
        return neighbors


class UniformIntegerHyperparameter(UniformMixin, IntegerHyperparameter):
    def __init__(self, name, lower, upper, default=None, q=None, log=False):
        self.lower = self.check_int(lower, "lower")
        self.upper = self.check_int(upper, "upper")
        if default is not None:
            default = self.check_int(default, name)
        if q is not None:
            if q < 1:
                warnings.warn("Setting quantization < 1 for Integer "
                              "Hyperparameter '%s' has no effect." %
                              name)
                self.q = None
            else:
                self.q = self.check_int(q, "q")
        else:
            self.q = None
        self.log = bool(log)

        if self.lower >= self.upper:
            raise ValueError("Upper bound %d must be larger than lower bound "
                             "%d for hyperparameter %s" %
                             (self.lower, self.upper, name))
        elif log and self.lower <= 0:
            raise ValueError("Negative lower bound (%d) for log-scale "
                             "hyperparameter %s is forbidden." %
                             (self.lower, name))

        super(UniformIntegerHyperparameter, self). \
            __init__(name, self.check_default(default))

        self.ufhp = UniformFloatHyperparameter(self.name,
                                               self.lower - 0.49999,
                                               self.upper + 0.49999,
                                               log=self.log, q=self.q,
                                               default=self.default)

    def __repr__(self):
        repr_str = six.StringIO()
        repr_str.write("%s, Type: UniformInteger, Range: [%s, %s], Default: %s"
                       % (self.name, str(self.lower),
                          str(self.upper), str(self.default)))
        if self.log:
            repr_str.write(", on log-scale")
        if self.q is not None:
            repr_str.write(", Q: %s" % str(np.int(self.q)))
        repr_str.seek(0)
        return repr_str.getvalue()

    def _sample(self, rs, size=None):
        value = self.ufhp._sample(rs, size=size)
        return value

    def _transform(self, vector):
        if np.isnan(vector):
            return None
        vector = self.ufhp._transform(vector)
        if self.q is not None:
            vector = int(np.round(vector / self.q, 0)) * self.q
        return int(np.round(vector, 0))

    def _inverse_transform(self, vector):
        return self.ufhp._inverse_transform(vector)

    def has_neighbors(self):
        if self.log:
            upper = np.exp(self.ufhp._upper)
            lower = np.exp(self.ufhp._lower)
        else:
            upper = self.ufhp._upper
            lower = self.ufhp._lower

        # If there is only one active value, this is not enough
        if upper - lower >= 1:
            return True
        else:
            return False

    def get_neighbors(self, value, rs, number=4, transform=False):
        neighbors = []
        while len(neighbors) < number:
            rejected = True
            iteration = 0
            while rejected:
                new_value = np.max((0, min(1, rs.normal(value, 0.2))))
                int_value = self._transform(value)
                new_int_value = self._transform(new_value)
                if int_value != new_int_value:
                    rejected = False
                elif iteration > 100000:
                    raise ValueError('Probably caught in an infinite loop.')

            if transform:
                neighbors.append(self._transform(new_value))
            else:
                neighbors.append(new_value)

        return neighbors


class NormalIntegerHyperparameter(NormalMixin, IntegerHyperparameter):
    def __init__(self, name, mu, sigma, default=None, q=None, log=False):
        self.mu = mu
        self.sigma = sigma
        if default is not None:
            default = self.check_int(default, name)
        if q is not None:
            if q < 1:
                warnings.warn("Setting quantization < 1 for Integer "
                              "Hyperparameter '%s' has no effect." %
                              name)
                self.q = None
            else:
                self.q = self.check_int(q, "q")
        else:
            self.q = None
        self.log = bool(log)

        super(NormalIntegerHyperparameter, self). \
            __init__(name, self.check_default(default))

        self.nfhp = NormalFloatHyperparameter(self.name,
                                              self.mu,
                                              self.sigma,
                                              log=self.log,
                                              q=self.q,
                                              default=self.default)

    def __repr__(self):
        repr_str = six.StringIO()
        repr_str.write("%s, Type: NormalInteger, Mu: %s Sigma: %s, Default: "
                       "%s" % (self.name, str(self.mu),
                               str(self.sigma), str(self.default)))
        if self.log:
            repr_str.write(", on log-scale")
        if self.q is not None:
            repr_str.write(", Q: %s" % str(self.q))
        repr_str.seek(0)
        return repr_str.getvalue()

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return all([self.name == other.name,
                        abs(self.mu - other.mu) < 0.00000001,
                        abs(self.sigma - other.sigma) < 0.00000001,
                        self.log == other.log,
                        self.q is None and other.q is None or
                        self.q is not None and other.q is not None and
                        self.q == other.q])
        else:
            return False

    def to_uniform(self, z=3):
        return UniformIntegerHyperparameter(self.name,
                                            self.mu - (z * self.sigma),
                                            self.mu + (z * self.sigma),
                                            default=self.default,
                                            q=self.q, log=self.log)

    def is_legal(self, value):
        if isinstance(value, int):
            return True
        else:
            return False

    def _sample(self, rs, size=None):
        return self.nfhp._sample(rs, size=size)

    def _transform(self, vector):
        if np.isnan(vector):
            return None
        vector = self.nfhp._transform(vector)
        return int(np.round(vector, 0))

    def _inverse_transform(self, vector):
        return self.nfhp._inverse_transform(vector)

    def has_neighbors(self):
        return True

    def get_neighbors(self, value, rs, number=4, transform=False):
        neighbors = []
        while len(neighbors) < number:
            rejected = True
            iteration = 0
            while rejected:
                iteration += 1
                new_value = rs.normal(value, self.sigma)
                int_value = self._transform(value)
                new_int_value = self._transform(new_value)
                if int_value != new_int_value:
                    rejected = False
                elif iteration > 100000:
                    raise ValueError('Probably caught in an infinite loop.')

            if transform:
                neighbors.append(self._transform(new_value))
            else:
                neighbors.append(new_value)


class CategoricalHyperparameter(Hyperparameter):
    # TODO add more magic for automated type recognition
    def __init__(self, name, choices, default=None):
        super(CategoricalHyperparameter, self).__init__(name)
        # TODO check that there is no bullshit in the choices!
        self.choices = choices
        self._num_choices = len(choices)
        self.default = self.check_default(default)

    def __repr__(self):
        repr_str = six.StringIO()
        repr_str.write("%s, Type: Categorical, Choices: {" % (self.name))
        for idx, choice in enumerate(self.choices):
            repr_str.write(str(choice))
            if idx < len(self.choices) - 1:
                repr_str.write(", ")
        repr_str.write("}")
        repr_str.write(", Default: ")
        repr_str.write(str(self.default))
        repr_str.seek(0)
        return repr_str.getvalue()

    def is_legal(self, value):
        if value in self.choices:
            return True
        else:
            return False

    def check_default(self, default):
        if default is None:
            return self.choices[0]
        elif self.is_legal(default):
            return default
        else:
            raise ValueError("Illegal default value %s" % str(default))

    def _sample(self, rs, size=None):
        return rs.randint(0, self._num_choices, size=size)

    def _transform(self, vector):
        if vector != vector:
            return None
        if np.equal(np.mod(vector, 1), 0):
            return self.choices[int(vector)]
        else:
            raise ValueError('Can only index the choices of the categorical '
                             'hyperparameter %s with an integer, but provided '
                             'the following float: %f' % (self, vector))

    def _inverse_transform(self, vector):
        if vector is None:
            return np.NaN
        return self.choices.index(vector)

    def has_neighbors(self):
        return len(self.choices) > 1

    def get_num_neighbors(self):
        return len(self.choices) - 1

    def get_neighbors(self, value, rs, number=np.inf, transform=False):
        neighbors = []
        if number < len(self.choices):
            while len(neighbors) < number:
                rejected = True
                index = int(value)
                while rejected:
                    neighbor_idx = rs.randint(0, self._num_choices)
                    if neighbor_idx != index:
                        rejected = False

                if transform:
                    candidate = self._transform(neighbor_idx)
                else:
                    candidate = float(neighbor_idx)

                if candidate in neighbors:
                    continue
                else:
                    neighbors.append(candidate)
        else:
            for candidate_idx, candidate_value in enumerate(self.choices):
                if int(value) == candidate_idx:
                    continue
                else:
                    if transform:
                        candidate = self._transform(candidate_idx)
                    else:
                        candidate = float(candidate_idx)

                    neighbors.append(candidate)

        return neighbors

