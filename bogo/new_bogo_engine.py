# -*- coding: utf-8 -*-
# New BoGo Engine - Vietnamese Text processing engine
#
# Copyright (c) 2012- Long T. Dam <longdt90@gmail.com>,
#                     Trung Ngo <ndtrung4419@gmail.com>
#
# This file is part of BoGo IBus Engine Project BoGo IBus Engine is
# free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# IBus-BoGo is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with IBus-BoGo. If not, see <http://www.gnu.org/licenses/>.

from .valid_vietnamese import is_valid_combination
from . import utils, accent, mark
import logging

Mark = mark.Mark
Accent = accent.Accent


class Action:
    UNDO = 3
    ADD_MARK = 2
    ADD_ACCENT = 1
    ADD_CHAR = 0


def is_processable(comps):
    # For now only check the last 2 components
    return is_valid_combination(('', comps[1], comps[2]), final_form=False)


def process_key(string, key, raw_key_sequence="", config=None):
    """
    Try to apply the transformations inferred from `key` to `string` with
    `raw_key_sequence` as a reference. `config` should be a dictionary-like
    object obtained from `..config.Config()`.

    returns (new string, new raw_key_sequence)

    >>> process_key('a', 'a', 'a', config=default_config)
    (â, aa)

    Note that when a key is an undo key, it won't get appended to
    `raw_key_sequence`.

    >>> process_key('â', 'a', 'aa', config=default_config)
    (aa, aa)
    """
    # TODO Figure out a way to remove the `string` argument.
    logging.debug("== In process_key() ==")
    logging.debug("key = %s", key)

    def default_return():
        return string + key, raw_key_sequence + key

    if config is None:
        return default_return()

    # NOTE to whoever reading this:
    # config.py is on our back here. If this module is ever used outside
    # this project, remember to port config.py as well.
    if config["input-method"] in config["default-input-methods"]:
        im = config["default-input-methods"][config["input-method"]]
    elif "custom-input-methods" in config and \
            config["input-method"] in config["custom-input-methods"]:
        im = config["custom-input-methods"][config["input-method"]]

    comps = separate(string)
    logging.debug("separate(string) = %s", str(comps))

    # if not is_processable(comps):
    #     return default_return()

    # Find all possible transformations this keypress can generate
    trans_list = get_transformation_list(key, im, raw_key_sequence)
    logging.debug("trans_list = %s", trans_list)

    # Then apply them one by one
    new_comps = list(comps)
    for trans in trans_list:
        new_comps = transform(new_comps, trans)

    logging.debug("new_comps: %s", str(new_comps))
    if new_comps == comps:
        tmp = list(new_comps)

        # If none of the transformations (if any) work
        # then this keystroke is probably an undo key.
        if can_undo(new_comps, trans_list):
            # The prefix "_" means undo.
            for trans in map(lambda x: "_" + x, trans_list):
                new_comps = transform(new_comps, trans)
    
            # TODO refactor
            if config["input-method"] == "telex" and \
                    len(raw_key_sequence) >= 1 and \
                    new_comps[1] and new_comps[1][-1].lower() == "u" and \
                    (raw_key_sequence[-1:]+key).lower() == "ww" and \
                    not (len(raw_key_sequence) >= 2 and
                         raw_key_sequence[-2].lower() == "u"):
                new_comps[1] = new_comps[1][:-1]

        if tmp == new_comps:
            raw_key_sequence += key
        new_comps = utils.append_comps(new_comps, key)
    else:
        raw_key_sequence += key

    logging.debug("%s, %s", utils.join(new_comps), raw_key_sequence)

    if config['skip-non-vietnamese'] == True and (key.isalpha() or key in im) and \
            not is_valid_combination(new_comps, final_form=False):
        return raw_key_sequence, raw_key_sequence
    else:
        return utils.join(new_comps), raw_key_sequence


def get_transformation_list(key, im, raw_key_sequence):
    """
        Return the list of transformations inferred from the entered key. The
        map between transform types and keys is given by module
        bogo_config (if exists) or by variable simple_telex_im

        if entered key is not in im, return "+key", meaning appending
        the entered key to current text
    """
    # if key in im:
    #     lkey = key
    # else:
    #     lkey = key.lower()
    lkey = key.lower()

    if lkey in im:
        if isinstance(im[lkey], list):
            trans_list = im[lkey]
        else:
            trans_list = [im[lkey]]

        for i, trans in enumerate(trans_list):
            if trans[0] == '<' and key.isalpha():
                trans_list[i] = trans[0] + utils.change_case(trans[1],
                                                             int(key.isupper()))

        if trans_list == ['_']:
            if len(raw_key_sequence) >= 2:
                # TODO Use takewhile()/dropwhile() to process the last IM keypress
                # instead of assuming it's the last key in raw_key_sequence.
                t = list(map(lambda x: "_" + x,
                             get_transformation_list(raw_key_sequence[-2], im,
                                                     raw_key_sequence[:-1])))
                # print(t)
                trans_list = t
            # else:
            #     trans_list = ['+' + key]

        return trans_list
    else:
        return ['+' + key]


def get_action(trans):
    """
    Return the action inferred from the transformation `trans`.
    and the factor going with this action
    An Action.ADD_MARK goes with a Mark
    while an Action.ADD_ACCENT goes with an Accent
    """
    # TODO: VIQR-like convention
    if trans[0] in ('<', '+'):
        return Action.ADD_CHAR, trans[1]
    if trans[0] == "_":
        return Action.UNDO, trans[1:]
    if len(trans) == 2:
        if trans[1] == '^':
            return Action.ADD_MARK, Mark.HAT
        if trans[1] == '+':
            return Action.ADD_MARK, Mark.BREVE
        if trans[1] == '*':
            return Action.ADD_MARK, Mark.HORN
        if trans[1] == "-":
            return Action.ADD_MARK, Mark.BAR
        # if trans[1] == "_":
        #     return Action.ADD_MARK, Mark.NONE
    else:
        if trans[0] == "\\":
            return Action.ADD_ACCENT, Accent.GRAVE
        if trans[0] == "/":
            return Action.ADD_ACCENT, Accent.ACUTE
        if trans[0] == "?":
            return Action.ADD_ACCENT, Accent.HOOK
        if trans[0] == "~":
            return Action.ADD_ACCENT, Accent.TIDLE
        if trans[0] == ".":
            return Action.ADD_ACCENT, Accent.DOT
        # if trans[0] == "_":
        #     return Action.ADD_ACCENT, Accent.NONE


def transform(comps, trans):
    """
    Transform the given string with transform type trans
    """
    logging.debug("== In transform() ==")
    components = list(comps)

    action, factor = get_action(trans)

    if action == Action.ADD_ACCENT:
        components = accent.add_accent(components, factor)
    elif action == Action.ADD_MARK and mark.is_valid_mark(components, trans):
        components = mark.add_mark(components, factor)

        # Handle uơ in "huơ", "thuở", "quở"
        # If the current word has no last consonant and the first consonant
        # is one of "h", "th" and the vowel is "ươ" then change the vowel into
        # "uơ", keeping case and accent. If an alphabet character is then added
        # into the word then change back to "ươ".
        #
        # NOTE: In the dictionary, these are the only words having this strange
        # vowel so we don't need to worry about other cases.
        if accent.remove_accent_string(components[1]).lower() == "ươ" and \
                not components[2] and components[0].lower() in ["h", "th"]:
            components[1] = ('u', 'U')[components[1][0].isupper()] + components[1][1]

    elif action == Action.ADD_CHAR:
        if trans[0] == "<":
            if not components[2]:
                # Only allow ư, ơ or ươ sitting alone in the middle part
                # and ['g', 'i', '']. If we want to type giowf = 'giờ', separate()
                # will create ['g', 'i', '']. Therefore we have to allow
                # components[1] == 'i'.
                if not components[1] or \
                        (components[1].lower(), trans[1].lower()) == ('ư', 'ơ') or \
                        (components[1].lower(), components[0].lower()) == ('i', 'g'):
                    components[1] += trans[1]
        else:
            components = utils.append_comps(components, factor)
            if factor.isalpha() and \
                    accent.remove_accent_string(components[1]).lower().startswith("uơ"):
                accent_list = map(accent.get_accent_char, components[1])
                components[1] = ('ư', 'Ư')[components[1][0].isupper()] + \
                    ('ơ', 'Ơ')[components[1][1].isupper()] + components[1][2:]
                for ac in accent_list:
                    accent.add_accent(components, ac)
    elif action == Action.UNDO:
        components = reverse(components, trans[1:])

    if action == Action.ADD_MARK or (action == Action.ADD_CHAR and factor.isalpha()):
        # TODO: rewrite this part in functional style
        # If there is any accent, remove and reapply it
        # because it is likely to be misplaced in previous transformations
        ac = accent.Accent.NONE
        for c in components[1]:
            ac = accent.get_accent_char(c)
            if ac:
                break
        if ac != accent.Accent.NONE:
            # Remove accent
            components = accent.add_accent(components, Accent.NONE)
            components = accent.add_accent(components, ac)

    return components


def separate(string):
    """
    Separate a string into smaller parts: first consonant (or garbage), vowel,
    last consonant (if any).

    >>> separate('tuong')
    ['t','uo','ng']
    >>> separate('ohmyfkinggod')
    ['ohmyfkingg','o','d']
    """
    def atomic_separate(string, last_chars, last_is_vowel):
        if string == "" or (last_is_vowel != utils.is_vowel(string[-1])):
            return (string, last_chars)
        else:
            return atomic_separate(string[:-1],
                                   string[-1] + last_chars, last_is_vowel)

    a = atomic_separate(string, "", False)
    b = atomic_separate(a[0], "", True)

    comps = [b[0], b[1], a[1]]

    if a[1] and not b[0] and not b[1]:
        comps.reverse()

    # 'gi' and 'q' need some special treatments
    # We want something like this:
    #     ['g', 'ia', ''] -> ['gi', 'a', '']
    if (comps[0] != '' and comps[1] != '') and \
        ((comps[0] in 'gG' and comps[1][0] in 'iI' and len(comps[1]) > 1) or
         (comps[0] in 'qQ' and comps[1][0] in 'uU')):
        comps[0] += comps[1][:1]
        comps[1] = comps[1][1:]

    return comps


def reverse(components, trans):
    """
    Reverse the effect of transformation 'trans' on 'components'
    If the transformation does not affect the components, return the original
    string.
    """

    action, factor = get_action(trans)
    comps = list(components)
    string = utils.join(comps)

    if action == Action.ADD_CHAR and string[-1].lower() == factor.lower():
        if comps[2]:
            i = 2
        elif comps[1]:
            i = 1
        else:
            i = 0
        comps[i] = comps[i][:-1]
    elif action == Action.ADD_ACCENT:
        comps = accent.add_accent(comps, Accent.NONE)
    elif action == Action.ADD_MARK:
        if factor == Mark.BAR:
            comps[0] = comps[0][:-1] + \
                mark.add_mark_char(comps[0][-1:], Mark.NONE)
        else:
            if mark.is_valid_mark(comps, trans):
                comps[1] = "".join([mark.add_mark_char(c, Mark.NONE)
                                    for c in comps[1]])
    return comps


def can_undo(comps, trans_list):
    """
    Return whether a components can be undone with one of the transformation in
    trans_list.
    """
    comps = list(comps)
    accent_list = list(map(accent.get_accent_char, comps[1]))
    mark_list = list(map(mark.get_mark_char, utils.join(comps)))
    action_list = list(map(lambda x: get_action(x), trans_list))

    a = [action for action in action_list if action[0] == Action.ADD_ACCENT and action[1] in accent_list]
    b = [action for action in action_list if action[0] == Action.ADD_MARK and action[1] in mark_list]
    c = [trans for trans in trans_list if
         trans[0] == "<" and trans[1].lower() in accent.remove_accent_string(comps[1]).lower()]

    if a != [] or b != [] or c != []:
        return True
    else:
        return False
