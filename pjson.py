from itertools import product
from ConfigSpace.configuration_space import ConfigurationSpace
from ConfigSpace.hyperparameters import CategoricalHyperparameter,NumericalHyperparameter, Constant, \
    IntegerHyperparameter, NormalIntegerHyperparameter, NormalFloatHyperparameter
from ConfigSpace.conditions import EqualsCondition, NotEqualsCondition, \
    InCondition, AndConjunction, OrConjunction, ConditionComponent
from ConfigSpace.forbidden import ForbiddenEqualsClause, \
    ForbiddenAndConjunction, ForbiddenInClause, AbstractForbiddenComponent, MultipleValueForbiddenClause
from math import log
import pyparsing
import six
import json

pp_param_name = pyparsing.Word(pyparsing.alphanums + "_" + "-" + "@" + "." + ":" + ";" + "\\" + "/" + "?" + "!" +
                               "$" + "%" + "&" + "*" + "+" + "<" + ">")


def build_categorical(param):
    # cat_template = "%s '--%s ' c (%s)"
    # return [param.name, cat_template % (param.name, param.name, ",".join([str(value) for value in param.choices]))]
    return [param.name, {"type": "categrical", "values": [value for value in param.choices], "default": param.default}]


def build_constant(param):
    # constant_template = "%s '--%s ' c (%s)"
    # return [param.name, constant_template % (param.name, param.name, param.value)]
    return [param.name, {"type": "constant", "value": param.value}]


def build_continuous(param):
    if type(param) in (NormalIntegerHyperparameter,
                       NormalFloatHyperparameter):
        param = param.to_uniform()

    if param.log is True:
        return [param.name, {"type": "continuous", "range": [param.lower, param.upper],
                             "log-scale": "true", "default": param.default}]
    else:
        return [param.name, {"type": "continuous", "range": [param.lower, param.upper],
                             "log-scale": "false", "default": param.default}]


def build_condition(condition):
    if not isinstance(condition, ConditionComponent):
        raise TypeError("build_condition must be called with an instance of "
                        "'%s', got '%s'" %
                        (ConditionComponent, type(condition)))

    # Findout type of parent
    pType = "integer"
    if condition.parent.__class__.__name__ == 'CategoricalHyperparameter':
        pType = 'categorical'
    if condition.parent.__class__.__name__ == 'UniformFloatHyperparameter':
        pType = 'continuous'

    print(type(condition).__name__)
    # Now handle the conditions SMAC can handle
    condition_template = " | %s %%in%% %s(%s) "
    if isinstance(condition, AndConjunction):
        raise NotImplementedError("This is not yet implemented!")
    else:
        if type(condition).__name__ == "EqualsCondition":
            return [condition.child.name, condition.parent.name, pType, condition.value]
        else:
            return [condition.child.name, condition.parent.name, pType, [value for value in condition.values]]


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
        condition_vars = build_condition(condition)  # [child, parent, ptype, vals]

        child = condition_vars[0]
        parent = condition_vars[1]
        pType = condition_vars[2]
        vals = condition_vars[3]
        if type(vals) == str:
            tmp = list()
            tmp.append(vals)
            vals = tmp

        if "dependsOn" in param_lines_dict[child]:
            param_lines_dict[child]["dependsOn"].append[{parent: {"type": pType, "values": vals}}]
        else:
            param_lines_dict[child]["dependsOn"] = [{parent: {"type": pType, "values": vals}}]

        if "affects" in param_lines_dict[parent]:
            param_lines_dict[parent]["affects"].append(child)
        else:
            param_lines_dict[parent]["affects"] = [child]

    with open('data.js', 'w') as outfile:
        dump = json.dumps(param_lines_dict, sort_keys=True, indent=4)
        outfile.write("var data_js = " + dump)

