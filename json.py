from itertools import product
from ConfigSpace.configuration_space import ConfigurationSpace
from ConfigSpace.hyperparameters import CategoricalHyperparameter,NumericalHyperparameter, Constant, \
    IntegerHyperparameter, NormalIntegerHyperparameter, NormalFloatHyperparameter
from ConfigSpace.conditions import EqualsCondition, NotEqualsCondition, \
    InCondition, AndConjunction, OrConjunction, ConditionComponent
from ConfigSpace.forbidden import ForbiddenEqualsClause, \
    ForbiddenAndConjunction, ForbiddenInClause, AbstractForbiddenComponent, MultipleValueForbiddenClause

import pyparsing
import six

pp_param_name = pyparsing.Word(pyparsing.alphanums + "_" + "-" + "@" + "." + ":" + ";" + "\\" + "/" + "?" + "!" +
                               "$" + "%" + "&" + "*" + "+" + "<" + ">")


def build_categorical(param):
    cat_template = "%s '--%s ' c (%s)"
    return [param.name, cat_template % (param.name, param.name, ",".join([str(value) for value in param.choices]))]


def build_constant(param):
    constant_template = "%s '--%s ' c (%s)"
    return [param.name, constant_template % (param.name, param.name, param.value)]


def build_continuous(param):
    if type(param) in (NormalIntegerHyperparameter,
                       NormalFloatHyperparameter):
        param = param.to_uniform()

    float_template = "%s '--%s ' r (%s, %s) "
    int_template = "%s '--%s ' i (%d, %d)"
    # if param.log:
    #     float_template += "l"
    #     int_template += "l"

    if param.q is not None:
        q_prefix = "Q%d_" % (int(param.q),)
    else:
        q_prefix = ""
    default = param.default

    if isinstance(param, IntegerHyperparameter):
        default = int(default)
        return [param.name, int_template % (param.name, param.name, param.lower,
                               param.upper)]
    else:
        return [param.name, float_template % (param.name, param.name, str(param.lower),
                                 str(param.upper))]


def build_condition(condition):
    if not isinstance(condition, ConditionComponent):
        raise TypeError("build_condition must be called with an instance of "
                        "'%s', got '%s'" %
                        (ConditionComponent, type(condition)))

    # Check if IRACE can handle the condition
    if isinstance(condition, OrConjunction):
        raise NotImplementedError("IRACE cannot handle OR conditions: %s" %
                                  (condition))
    if isinstance(condition, NotEqualsCondition):
        raise NotImplementedError("IRACE cannot handle != conditions: %s" %
                                  (condition))

    # Findout type of parent
    pType = "i"
    if condition.parent.__class__.__name__ == 'CategoricalHyperparameter':
        pType = 'c'
    if condition.parent.__class__.__name__ == 'UniformFloatHyperparameter':
        pType = 'r'

    # Now handle the conditions SMAC can handle
    condition_template = " | %s %%in%% %s(%s) "
    if isinstance(condition, AndConjunction):
        raise NotImplementedError("This is not yet implemented!")
    elif isinstance(condition, InCondition):
        return [condition.child.name, condition_template % (
                                     condition.parent.name,
                                     pType,
                                     ", ".join(condition.values))]
    elif isinstance(condition, EqualsCondition):
        return [condition.child.name, condition_template % (
                                     condition.parent.name,
                                     pType,
                                     condition.value)]


def build_forbidden(clause):
    if not isinstance(clause, AbstractForbiddenComponent):
        raise TypeError("build_forbidden must be called with an instance of "
                        "'%s', got '%s'" %
                        (AbstractForbiddenComponent, type(clause)))

    if not isinstance(clause, (ForbiddenEqualsClause, ForbiddenAndConjunction)):
        raise NotImplementedError("SMAC cannot handle '%s' of type %s" %
                                  str(clause), (type(clause)))

    retval = six.StringIO()
    retval.write("{")
    # Really simple because everything is an AND-conjunction of equals
    # conditions
    dlcs = clause.get_descendant_literal_clauses()
    for dlc in dlcs:
        if retval.tell() > 1:
            retval.write(", ")
        retval.write("%s=%s" % (dlc.hyperparameter.name, dlc.value))
    retval.write("}")
    retval.seek(0)
    return retval.getvalue()


def write(configuration_space):
    if not isinstance(configuration_space, ConfigurationSpace):
        raise TypeError("pcs_parser.write expects an instance of %s, "
                        "you provided '%s'" % (ConfigurationSpace,
                                               type(configuration_space)))

    param_lines_dict = dict()
    condition_lines_dict = dict()
    forbidden_lines = []
    for hyperparameter in configuration_space.get_hyperparameters():
        # Check if the hyperparameter names are valid IRACE names!
        try:
            pp_param_name.parseString(hyperparameter.name)
        except pyparsing.ParseException:
            raise ValueError(
                "Illegal hyperparameter name for IRACE: %s" % hyperparameter.name)

        if isinstance(hyperparameter, NumericalHyperparameter):
            # print "building countinuous param"
            param_vars = build_continuous(hyperparameter)
            param_lines_dict.update({param_vars[0]: param_vars[1]})
        elif isinstance(hyperparameter, CategoricalHyperparameter):
            # print "building categorical param"
            param_vars = build_categorical(hyperparameter)
            param_lines_dict.update({param_vars[0]: param_vars[1]})
        elif isinstance(hyperparameter, Constant):
            # print "building constant param"
            param_vars = build_constant(hyperparameter)
            param_lines_dict.update({param_vars[0]: param_vars[1]})
        else:
            raise TypeError("Unknown type: %s (%s)" % (
                type(hyperparameter), hyperparameter))

    for condition in configuration_space.get_conditions():
        condition_vars = build_condition(condition)
        condition_lines_dict.update({condition_vars[0]: condition_vars[1]})

    for forbidden_clause in configuration_space.forbidden_clauses:
        # Convert in-statement into two or more equals statements
        dlcs = forbidden_clause.get_descendant_literal_clauses()
        # First, get all in statements and convert them to equal statements
        in_statements = []
        other_statements = []
        for dlc in dlcs:
            if isinstance(dlc, MultipleValueForbiddenClause):
                if not isinstance(dlc, ForbiddenInClause):
                    raise ValueError("IRACE cannot handle this forbidden "
                                     "clause: %s" % dlc)
                in_statements.append(
                    [ForbiddenEqualsClause(dlc.hyperparameter, value)
                     for value in dlc.values])
            else:
                other_statements.append(dlc)
        # Second, create the product of all elements in the IN statements,
        # create a ForbiddenAnd and add all ForbiddenEquals
        if len(in_statements) > 0:
            for i, p in enumerate(product(*in_statements)):
                all_forbidden_clauses = list(p) + other_statements
                f = ForbiddenAndConjunction(*all_forbidden_clauses)
                forbidden_lines.append(build_forbidden(f))
        else:
            forbidden_lines.append(build_forbidden(forbidden_clause))

    param_lines = six.StringIO()
    for param in param_lines_dict:
        if param in condition_lines_dict:
            # print(param_lines_dict[param] + condition_lines_dict[param])
            param_lines_dict[param] = param_lines_dict[param] + condition_lines_dict[param] + '\n'
        else:
            param_lines_dict[param] += '\n'
        param_lines.write(param_lines_dict[param])

    # TODO: check if irace supports forbidden lines

    return param_lines.getvalue()