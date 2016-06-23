#!/usr/bin/env python

from ConfigSpace.configuration_space import ConfigurationSpace
from ConfigSpace.hyperparameters import CategoricalHyperparameter, UniformIntegerHyperparameter, \
    UniformFloatHyperparameter, IntegerHyperparameter, NormalIntegerHyperparameter, NormalFloatHyperparameter
from ConfigSpace.conditions import EqualsCondition, NotEqualsCondition, InCondition, AndConjunction, OrConjunction, \
    ConditionComponent
from ConfigSpace.forbidden import ForbiddenEqualsClause, ForbiddenAndConjunction, AbstractForbiddenComponent

from collections import OrderedDict
import pyparsing
import six


__authors__ = ["Katharina Eggensperger", "Matthias Feurer"]
__contact__ = "automl.org"

# Build pyparsing expressions for paramsparams
pp_param_name = pyparsing.Word(pyparsing.alphanums + "_" + "-" + "@" + "." + ":" + ";" + "\\" + "/" + "?" + "!" +
                               "$" + "%" + "&" + "*" + "+" + "<" + ">")
pp_digits = "0123456789"
pp_plusorminus = pyparsing.Literal('+') | pyparsing.Literal('-')
pp_int = pyparsing.Combine(pyparsing.Optional(pp_plusorminus) + pyparsing.Word(pp_digits))
pp_float = pyparsing.Combine(pyparsing.Optional(pp_plusorminus) + pyparsing.Optional(pp_int) + "." + pp_int)
pp_eorE = pyparsing.Literal('e') | pyparsing.Literal('E')
pp_floatorint = pp_float | pp_int
pp_e_notation = pyparsing.Combine(pp_floatorint + pp_eorE + pp_int)
pp_number = pp_e_notation | pp_float | pp_int
pp_numberorname = pp_number | pp_param_name
pp_il = pyparsing.Word("il")
pp_choices = pp_param_name + pyparsing.Optional(pyparsing.OneOrMore("," + pp_param_name))

pp_cont_param = pp_param_name + "[" + pp_number + "," + pp_number + "]" + \
    "[" + pp_number + "]" + pyparsing.Optional(pp_il)
pp_cat_param = pp_param_name + "{" + pp_choices + "}" + "[" + pp_param_name + "]"
pp_condition = pp_param_name + "|" + pp_param_name + "in" + "{" + pp_choices + "}"
pp_forbidden_clause = "{" + pp_param_name + "=" + pp_numberorname + \
    pyparsing.Optional(pyparsing.OneOrMore("," + pp_param_name + "=" + pp_numberorname)) + "}"


def build_categorical(param):
    cat_template = "%s {%s} [%s]"
    return cat_template % (param.name,
                           ", ".join([str(value) for value in param.choices]),
                           str(param.default))


def build_constant(param):
    constant_template = "%s {%s} [%s]"
    return constant_template % (param.name, param.value, param.value)


def build_continuous(param):
    if type(param) in (NormalIntegerHyperparameter,
                       NormalFloatHyperparameter):
        param = param.to_uniform()

    float_template = "%s%s [%s, %s] [%s]"
    int_template = "%s%s [%d, %d] [%d]i"
    if param.log:
        float_template += "l"
        int_template += "l"

    if param.q is not None:
        q_prefix = "Q%d_" % (int(param.q),)
    else:
        q_prefix = ""
    default = param.default

    if isinstance(param, IntegerHyperparameter):
        default = int(default)
        return int_template % (q_prefix, param.name, param.lower,
                               param.upper, default)
    else:
        return float_template % (q_prefix, param.name, str(param.lower),
                                 str(param.upper), str(default))


def build_condition(condition):
    if not isinstance(condition, ConditionComponent):
        raise TypeError("build_condition must be called with an instance of "
                        "'%s', got '%s'" %
                        (ConditionComponent, type(condition)))

    # Check if SMAC can handle the condition
    if isinstance(condition, OrConjunction):
        raise NotImplementedError("SMAC cannot handle OR conditions: %s" %
                                  (condition))
    if isinstance(condition, NotEqualsCondition):
        raise NotImplementedError("SMAC cannot handle != conditions: %s" %
                                 (condition))

    # Now handle the conditions SMAC can handle
    condition_template = "%s | %s in {%s}"
    if isinstance(condition, AndConjunction):
        raise NotImplementedError("This is not yet implemented!")
    elif isinstance(condition, InCondition):
        return condition_template % (condition.child.name,
                                     condition.parent.name,
                                     ", ".join(condition.values))
    elif isinstance(condition, EqualsCondition):
        return condition_template % (condition.child.name,
                                     condition.parent.name,
                                     condition.value)


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


def read(pcs_string, debug=False):
    configuration_space = ConfigurationSpace()
    conditions = []
    forbidden = []

    # some statistics
    ct = 0
    cont_ct = 0
    cat_ct = 0
    line_ct = 0

    for line in pcs_string:
        line_ct += 1

        if "#" in line:
            # It contains a comment
            pos = line.find("#")
            line = line[:pos]

        # Remove quotes and whitespaces at beginning and end
        line = line.replace('"', "").replace("'", "")
        line = line.strip()

        if "|" in line:
            # It's a condition
            try:
                c = pp_condition.parseString(line)
                conditions.append(c)
            except pyparsing.ParseException:
                raise NotImplementedError("Could not parse condition: %s" % line)
            continue
        if "}" not in line and "]" not in line:
            continue
        if line.startswith("{") and line.endswith("}"):
            forbidden.append(line)
            continue
        if len(line.strip()) == 0:
            continue

        ct += 1
        param = None

        create = {"int": UniformIntegerHyperparameter,
                  "float": UniformFloatHyperparameter,
                  "categorical": CategoricalHyperparameter}

        try:
            param_list = pp_cont_param.parseString(line)
            il = param_list[9:]
            if len(il) > 0:
                il = il[0]
            param_list = param_list[:9]
            name = param_list[0]
            lower = float(param_list[2])
            upper = float(param_list[4])
            paramtype = "int" if "i" in il else "float"
            log = True if "l" in il else False
            default = float(param_list[7])
            param = create[paramtype](name=name, lower=lower, upper=upper,
                                      q=None, log=log, default=default)
            cont_ct += 1
        except pyparsing.ParseException:
            pass

        try:
            param_list = pp_cat_param.parseString(line)
            name = param_list[0]
            choices = [c for c in param_list[2:-4:2]]
            default = param_list[-2]
            param = create["categorical"](name=name, choices=choices,
                                          default=default)
            cat_ct += 1
        except pyparsing.ParseException:
            pass

        if param is None:
            raise NotImplementedError("Could not parse: %s" % line)

        configuration_space.add_hyperparameter(param)

    for clause in forbidden:
        # TODO test this properly!
        # TODO Add a try/catch here!
        # noinspection PyUnusedLocal
        param_list = pp_forbidden_clause.parseString(clause)
        tmp_list = []
        clause_list = []
        for value in param_list[1:]:
            if len(tmp_list) < 3:
                tmp_list.append(value)
            else:
                # So far, only equals is supported by SMAC
                if tmp_list[1] == '=':
                    # TODO maybe add a check if the hyperparameter is
                    # actually in the configuration space
                    clause_list.append(ForbiddenEqualsClause(
                        configuration_space.get_hyperparameter(tmp_list[0]),
                        tmp_list[2]))
                else:
                    raise NotImplementedError()
                tmp_list = []
        configuration_space.add_forbidden_clause(ForbiddenAndConjunction(
            *clause_list))

    #Now handle conditions
    # If there are two conditions for one child, these two conditions are an
    # AND-conjunction of conditions, thus we have to connect them
    conditions_per_child = OrderedDict()
    for condition in conditions:
        child_name = condition[0]
        if child_name not in conditions_per_child:
            conditions_per_child[child_name] = list()
        conditions_per_child[child_name].append(condition)

    for child_name in conditions_per_child:
        condition_objects = []
        for condition in conditions_per_child[child_name]:
            child = configuration_space.get_hyperparameter(child_name)
            parent_name = condition[2]
            parent = configuration_space.get_hyperparameter(parent_name)
            restrictions = condition[5:-1:2]

            # TODO: cast the type of the restriction!
            if len(restrictions) == 1:
                condition = EqualsCondition(child, parent, restrictions[0])
            else:
                condition = InCondition(child, parent, values=restrictions)
            condition_objects.append(condition)

        # Now we have all condition objects for this child, so we can build a
        #  giant AND-conjunction of them (if number of conditions >= 2)!

        if len(condition_objects) > 1:
            and_conjunction = AndConjunction(*condition_objects)
            configuration_space.add_condition(and_conjunction)
        else:
            configuration_space.add_condition(condition_objects[0])

    return configuration_space


