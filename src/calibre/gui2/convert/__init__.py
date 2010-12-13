#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap
from functools import partial

from PyQt4.Qt import QWidget, QSpinBox, QDoubleSpinBox, QLineEdit, QTextEdit, \
    QCheckBox, QComboBox, Qt, QIcon, pyqtSignal, QLabel

from calibre.customize.conversion import OptionRecommendation
from calibre.ebooks.conversion.config import load_defaults, \
        save_defaults as save_defaults_, \
    load_specifics, GuiRecommendations
from calibre import prepare_string_for_xml
from calibre.customize.ui import plugin_for_input_format

def config_widget_for_input_plugin(plugin):
    name = plugin.name.lower().replace(' ', '_')
    try:
        return __import__('calibre.gui2.convert.'+name,
                fromlist=[1]).PluginWidget
    except ImportError:
        pass

def bulk_defaults_for_input_format(fmt):
    plugin = plugin_for_input_format(fmt)
    if plugin is not None:
        w = config_widget_for_input_plugin(plugin)
        if w is not None:
            return load_defaults(w.COMMIT_NAME)
    return {}



class Widget(QWidget):

    TITLE = _('Unknown')
    ICON  = I('config.png')
    HELP  = ''
    COMMIT_NAME = None

    changed_signal = pyqtSignal()
    set_help = pyqtSignal(object)

    def __init__(self, parent, options):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        self._options = options
        self._name = self.commit_name = self.COMMIT_NAME
        assert self._name is not None
        self._icon = QIcon(self.ICON)
        for name in self._options:
            if not hasattr(self, 'opt_'+name):
                raise Exception('Option %s missing in %s'%(name,
                    self.__class__.__name__))
            self.connect_gui_obj(getattr(self, 'opt_'+name))

    def initialize_options(self, get_option, get_help, db=None, book_id=None):
        '''
        :param get_option: A callable that takes one argument: the option name
        and returns the corresponding OptionRecommendation.
        :param get_help: A callable that takes the option name and return a help
        string.
        '''
        defaults = load_defaults(self._name)
        defaults.merge_recommendations(get_option, OptionRecommendation.LOW,
                self._options)

        if db is not None:
            specifics = load_specifics(db, book_id)
            specifics.merge_recommendations(get_option, OptionRecommendation.HIGH,
                    self._options, only_existing=True)
            defaults.update(specifics)


        self.apply_recommendations(defaults)
        self.setup_help(get_help)

        def process_child(child):
            for g in child.children():
                if isinstance(g, QLabel):
                    buddy = g.buddy()
                    if buddy is not None and hasattr(buddy, '_help'):
                        g._help = buddy._help
                        htext = unicode(buddy.toolTip()).strip()
                        g.setToolTip(htext)
                        g.setWhatsThis(htext)
                        g.__class__.enterEvent = lambda obj, event: self.set_help(getattr(obj, '_help', obj.toolTip()))
                else:
                    process_child(g)
        process_child(self)


    def restore_defaults(self, get_option):
        defaults = GuiRecommendations()
        defaults.merge_recommendations(get_option, OptionRecommendation.LOW,
                self._options)
        self.apply_recommendations(defaults)

    def commit_options(self, save_defaults=False):
        recs = self.create_recommendations()
        if save_defaults:
            save_defaults_(self.commit_name, recs)
        return recs

    def create_recommendations(self):
        recs = GuiRecommendations()
        for name in self._options:
            gui_opt = getattr(self, 'opt_'+name, None)
            if gui_opt is None: continue
            recs[name] = self.get_value(gui_opt)
        return recs

    def apply_recommendations(self, recs):
        for name, val in recs.items():
            gui_opt = getattr(self, 'opt_'+name, None)
            if gui_opt is None: continue
            self.set_value(gui_opt, val)
            if name in getattr(recs, 'disabled_options', []):
                gui_opt.setDisabled(True)


    def get_value(self, g):
        from calibre.gui2.convert.xpath_wizard import XPathEdit
        from calibre.gui2.convert.regex_builder import RegexEdit
        ret = self.get_value_handler(g)
        if ret != 'this is a dummy return value, xcswx1avcx4x':
            return ret
        if isinstance(g, (QSpinBox, QDoubleSpinBox)):
            return g.value()
        elif isinstance(g, (QLineEdit, QTextEdit)):
            func = getattr(g, 'toPlainText', getattr(g, 'text', None))()
            ans = unicode(func).strip()
            if not ans:
                ans = None
            return ans
        elif isinstance(g, QComboBox):
            return unicode(g.currentText())
        elif isinstance(g, QCheckBox):
            return bool(g.isChecked())
        elif isinstance(g, XPathEdit):
            return g.xpath if g.xpath else None
        elif isinstance(g, RegexEdit):
            return g.regex if g.regex else None
        else:
            raise Exception('Can\'t get value from %s'%type(g))

    def gui_obj_changed(self, gui_obj, *args):
        self.changed_signal.emit()

    def connect_gui_obj(self, g):
        f = partial(self.gui_obj_changed, g)
        try:
            self.connect_gui_obj_handler(g, f)
            return
        except NotImplementedError:
            pass
        from calibre.gui2.convert.xpath_wizard import XPathEdit
        from calibre.gui2.convert.regex_builder import RegexEdit
        if isinstance(g, (QSpinBox, QDoubleSpinBox)):
            g.valueChanged.connect(f)
        elif isinstance(g, (QLineEdit, QTextEdit)):
            g.textChanged.connect(f)
        elif isinstance(g, QComboBox):
            g.editTextChanged.connect(f)
            g.currentIndexChanged.connect(f)
        elif isinstance(g, QCheckBox):
            g.stateChanged.connect(f)
        elif isinstance(g, (XPathEdit, RegexEdit)):
            g.edit.editTextChanged.connect(f)
            g.edit.currentIndexChanged.connect(f)
        else:
            raise Exception('Can\'t connect %s'%type(g))

    def connect_gui_obj_handler(self, gui_obj, slot):
        raise NotImplementedError()

    def set_value(self, g, val):
        from calibre.gui2.convert.xpath_wizard import XPathEdit
        from calibre.gui2.convert.regex_builder import RegexEdit
        if self.set_value_handler(g, val):
            return
        if isinstance(g, (QSpinBox, QDoubleSpinBox)):
            g.setValue(val)
        elif isinstance(g, (QLineEdit, QTextEdit)):
            if not val: val = ''
            getattr(g, 'setPlainText', g.setText)(val)
            getattr(g, 'setCursorPosition', lambda x: x)(0)
        elif isinstance(g, QComboBox) and val:
            idx = g.findText(val, Qt.MatchFixedString)
            if idx < 0:
                g.addItem(val)
                idx = g.findText(val, Qt.MatchFixedString)
            g.setCurrentIndex(idx)
        elif isinstance(g, QCheckBox):
            g.setCheckState(Qt.Checked if bool(val) else Qt.Unchecked)
        elif isinstance(g, (XPathEdit, RegexEdit)):
            g.edit.setText(val if val else '')
        else:
            raise Exception('Can\'t set value %s in %s'%(repr(val),
                unicode(g.objectName())))
        self.post_set_value(g, val)

    def set_help(self, msg):
        if msg and getattr(msg, 'strip', lambda:True)():
            try:
                self.set_help.emit(msg)
            except:
                pass

    def setup_help(self, help_provider):
        w = textwrap.TextWrapper(80)
        for name in self._options:
            g = getattr(self, 'opt_'+name, None)
            if g is None:
                continue
            help = help_provider(name)
            if not help: continue
            g._help = help
            htext = u'<div>%s</div>'%prepare_string_for_xml(
                    '\n'.join(w.wrap(help)))
            g.setToolTip(htext)
            g.setWhatsThis(htext)
            g.__class__.enterEvent = lambda obj, event: self.set_help(getattr(obj, '_help', obj.toolTip()))


    def set_value_handler(self, g, val):
        return False

    def post_set_value(self, g, val):
        pass

    def get_value_handler(self, g):
        return 'this is a dummy return value, xcswx1avcx4x'

    def post_get_value(self, g):
        pass

    def break_cycles(self):
        self.db = None

    def pre_commit_check(self):
        return True

    def commit(self, save_defaults=False):
        return self.commit_options(save_defaults)

    def config_title(self):
        return self.TITLE

    def config_icon(self):
        return self._icon

