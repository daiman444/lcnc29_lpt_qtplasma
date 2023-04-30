############################
# **** IMPORT SECTION **** #
############################

import os
import subprocess
import hal
import linuxcnc
import math

from hal_glib import GStat
from PyQt5 import QtCore, QtWidgets
from qtvcp.widgets.mdi_line import MDILine as MDI_WIDGET
from qtvcp.widgets.gcode_editor import GcodeEditor as GCODE
from qtvcp.widgets.stylesheeteditor import  StyleSheetEditor as SSE
from qtvcp.lib.keybindings import Keylookup
from qtvcp.lib.aux_program_loader import Aux_program_loader
from qtvcp.core import Status, Action, Info


# Set up logging
from qtvcp import logger
LOG = logger.getLogger(__name__)

# Set the log level for this module
#LOG.setLevel(logger.INFO) # One of DEBUG, INFO, WARNING, ERROR, CRITICAL

###########################################
# **** instantiate libraries section **** #
###########################################

KEYBIND = Keylookup()
STATUS = Status()
ACTION = Action()
INFO = Info()
STYLEEDITOR = SSE()

TCLPATH = os.environ['LINUXCNC_TCL_DIR']
INIPATH = os.environ.get('INI_FILE_NAME', '/dev/null')

GSTAT = GStat()
###################################
# **** HANDLER CLASS SECTION **** #
###################################

class HandlerClass:
    ########################
    # **** INITIALIZE **** #
    ########################
    # widgets allows access to  widgets from the qtvcp files
    # at this point the widgets and hal pins are not instantiated
    def __init__(self, halcomp, widgets, paths):
        self.halcomp = halcomp
        self.w = widgets
        self.PATHS = paths
        self.stat = linuxcnc.stat()
        self.cmd = linuxcnc.command()
        self.inifile = linuxcnc.ini(INIPATH)
        self.coordinates = self.inifile.find('TRAJ', 'COORDINATES')
        self.g5x_dro = 'g54'
        self.mdi_pbuttons = ('pb_g0x0y0_zsafe', 'pb_g92x0y0z0', 'pb_g92x0',
                             'pb_g92y0', 'pb_g92z0', 'pb_g53xmax_ymax',
                             )


    ##########################################
    # Special Functions called from QTSCREEN
    ##########################################

    # at this point:
    # the widgets are instantiated.
    # the HAL pins are built but HAL is not set ready
    def initialized__(self):
        KEYBIND.add_call('Key_F12', 'on_keycall_F12')
        self.w.pb_estop.setCheckable(True)
        self.w.pb_estop.setChecked(True)
        self.w.pb_estop.toggled.connect(self.estop_change)
        self.w.pb_power.setCheckable(True)
        self.w.pb_power.setChecked(False)
        self.w.pb_power.setEnabled(False)
        self.w.pb_power.toggled.connect(self.power_state)
        self.w.pb_home_all.setCheckable(True)
        self.w.pb_home_all.setChecked(False)
        self.w.pb_home_all.setEnabled(False)
        self.w.pb_home_all.toggled.connect(self.homing_state)
        self.w.screen_options.setProperty('play_sound_option', False)
        self.w.pb_gx_plane.clicked.connect(self.g5x_dro_change)
        self.w.sw_other.setCurrentIndex(0)
        self.w.pb_gcode_tab.clicked.connect(lambda: self.sw_other_tab_change(0))
        self.w.pb_mdi_tab.clicked.connect(lambda: self.sw_other_tab_change(1))
        self.w.pb_settings_tab.clicked.connect(lambda: self.sw_other_tab_change(2))
        self.w.pb_gcode_load.clicked.connect(lambda: self.gcode_tab_pbuttons('load'))
        self.w.pb_gcode_edit.clicked.connect(lambda: self.gcode_tab_pbuttons('edit'))
        self.w.pb_gcode_reload.clicked.connect(lambda: self.gcode_tab_pbuttons('reload'))
        self.w.pb_halshow.clicked.connect(lambda: self.settings_tab_buttons('halshow'))
        self.w.pb_halscope.clicked.connect(lambda: self.settings_tab_buttons('halscope'))
        self.w.pb_halmeter.clicked.connect(lambda: self.settings_tab_buttons('halmeter'))
        self.w.pb_status.clicked.connect(lambda: self.settings_tab_buttons('status'))
        self.w.pb_calibration.clicked.connect(lambda: self.settings_tab_buttons('calibration'))

        # MDI commands for coordinates
        for i in self.mdi_pbuttons:
            command = i.replace('pb_', '')
            self.w[i].clicked.connect(lambda w, cmd=command: self.mdi_commands(cmd))
        STATUS.connect('periodic', self.motion_mode)
        STATUS.connect('state-estop', lambda w: self.estop_state(True))


    def estop_state(self, state):
        if isinstance(state, bool):
            if state:
                self.w.pb_estop.setChecked(True)
                self.w.pb_power.setChecked(False)
                self.w.pb_power.setEnabled(False)
                self.w.pb_home_all.setEnabled(False)

    def estop_change(self, state):
        if isinstance(state, bool):
            if state:
                self.cmd.state(linuxcnc.STATE_ESTOP)
                self.w.pb_power.setEnabled(False)
                self.w.pb_power.setChecked(False)
            else:
                self.cmd.state(linuxcnc.STATE_ESTOP_RESET)
                self.w.pb_power.setEnabled(True)

    def power_state(self, state):
        if isinstance(state, bool):
            if state:
                self.cmd.state(linuxcnc.STATE_ON)
                self.w.pb_home_all.setEnabled(True)
            else:
                self.cmd.state(linuxcnc.STATE_OFF)

    def homing_state(self, state):
        self.stat.poll()
        if isinstance(state, bool) and linuxcnc.MODE_MANUAL:
            if state:
                self.cmd.teleop_enable(False)
                self.cmd.home(-1)
                self.cmd.wait_complete()
                self.cmd.teleop_enable(True)
                self.cmd.wait_complete()
            else:
                self.cmd.teleop_enable(False)
                self.cmd.unhome(-1)
                self.cmd.wait_complete()
        self.stat.poll()

    def g5x_dro_change(self):
        if self.g5x_dro == 'g54':
            self.g5x_dro = 'g53'
            self.w.pb_gx_plane.setText('G53')
        else:
            self.g5x_dro = 'g54'
            self.w.pb_gx_plane.setText('G54')
        self.w.label_5.setText(str(self.g5x_dro))

# TODO доделаль вызовы движения для кнопок dro
    def motion_mode(self, *args, **kwargs):
        if self.stat.motion_mode == 1:
            self.show_joints()
        else:
            self.show_axes()

    def show_joints(self, *args, **kwargs):
        self.stat.poll()
        pos = self.stat.joint_position
        join_0 = pos[0]
        join_1 = pos[1]
        join_2 = pos[2]
        join_3 = pos[3]
        coord = (join_0, join_1, join_2, join_3)
        for i in range(0, 4):
            self.w['lbl_axis_%s' % i].close()
            self.w['dro_label_%s' % i].close()
            self.w['pb_jog_%s_plus' % i].close()
            self.w['pb_jog_%s_minus' % i].close()
        for i in range(0, len(self.coordinates)):
            self.w['lbl_axis_%s' % i].show()
            self.w['lbl_axis_%s' % i].setText('%s' % i)
            self.w['dro_label_%s' % i].show()
            self.w['dro_label_%s' % i].setText('%.2f' % coord[i])
            self.w['pb_jog_%s_plus' % i].show()
            self.w['pb_jog_%s_minus' % i].show()


    def show_axes(self, *args, **kwargs):
        self.stat.poll()
        pos = self.stat.actual_position
        offset = self.stat.g92_offset
        if self.g5x_dro == 'g54':
            x = pos[0] - offset[0]
            y = pos[1] - offset[1]
            z = pos[2] - offset[2]
            coord = (x, y, z,)
        else:
            x = pos[0]
            y = pos[1]
            z = pos[2]
            coord = (x, y, z,)
        for i in range(0, 4):
            self.w['lbl_axis_%s' % i].close()
            self.w['dro_label_%s' % i].close()
            self.w['pb_jog_%s_plus' % i].close()
            self.w['pb_jog_%s_minus' % i].close()
        for i in range(0, len(set(self.coordinates))):
            axis_name = "XYZ"[i]
            self.w['lbl_axis_%s' % i].show()
            self.w['lbl_axis_%s' % i].setText('%s'% axis_name)
            self.w['dro_label_%s' % i].show()
            self.w['dro_label_%s' % i].setText('%.2f' % coord[i])
            self.w['pb_jog_%s_plus' % i].show()
            self.w['pb_jog_%s_minus' % i].show()

    def mdi_commands(self, mdi):
        if mdi == 'g53xmax_ymax':
            y_coord = self.inifile.find('AXIS_Y', 'MAX_LIMIT')
            x_max = self.inifile.find('AXIS_X', 'MAX_LIMIT')
            x_min = self.inifile.find('AXIS_X', 'MIN_LIMIT')
            if abs(float(x_min)) > float(x_max):
                x_coord = x_min
            else:
                x_coord = x_max
            mdi = 'g53g0 x %s y %s' % (x_coord, y_coord)
        if mdi == 'g0x0y0_zsafe':
            safe = self.inifile.find('UD_PARAMS', 'SAFE_Z')
            mdi = mdi.replace('_zsafe', 'z %s' % safe)
        self.cmd.mode(linuxcnc.MODE_MDI)
        self.cmd.wait_complete()
        self.cmd.mdi('%s' % mdi)
        while not GSTAT.is_interp_idle():
            self.w.gcodegraphics.updateGL()
            QtWidgets.QApplication.processEvents()
        self.cmd.mode(linuxcnc.MODE_MANUAL)

    def sw_other_tab_change(self, num):
        for i in range(0, 4):
            if i == num:
                self.w.sw_other.setCurrentIndex(i)

    def gcode_tab_pbuttons(self, pbutton):
        if pbutton == 'load':
            STATUS.emit('dialog-request', {'NAME':'LOAD', 'ID':None})
        elif pbutton == 'edit':
            os.popen('gedit %s' % self.stat.file)
        elif pbutton == 'reload':
            STATUS.emit('reload-display')




    def settings_tab_buttons(self, pbutton):
        process = ['halshow', 'halscope', 'halmeter', ]
        for i in process:
            if i == pbutton:
                os.popen('/usr/bin/%s' % i)
        if pbutton == 'calibration':
            os.popen("tclsh %s/bin/emccalib.tcl -- -ini %s > /dev/null &" % (TCLPATH, INIPATH), "w")
        if pbutton == 'status':
            os.popen("linuxcnctop  > /dev/null &", "w")

    def processed_key_event__(self,receiver,event,is_pressed,key,code,shift,cntrl):
        # when typing in MDI, we don't want keybinding to call functions
        # so we catch and process the events directly.
        # We do want ESC, F1 and F2 to call keybinding functions though
        if code not in(QtCore.Qt.Key_Escape,QtCore.Qt.Key_F1 ,QtCore.Qt.Key_F2,
                    QtCore.Qt.Key_F3,QtCore.Qt.Key_F5,QtCore.Qt.Key_F5):

            # search for the top widget of whatever widget received the event
            # then check if it's one we want the keypress events to go to
            flag = False
            receiver2 = receiver
            while receiver2 is not None and not flag:
                if isinstance(receiver2, QtWidgets.QDialog):
                    flag = True
                    break
                if isinstance(receiver2, MDI_WIDGET):
                    flag = True
                    break
                if isinstance(receiver2, GCODE):
                    flag = True
                    break
                receiver2 = receiver2.parent()

            if flag:
                if isinstance(receiver2, GCODE):
                    # if in manual do our keybindings - otherwise
                    # send events to gcode widget
                    if STATUS.is_man_mode() == False:
                        if is_pressed:
                            receiver.keyPressEvent(event)
                            event.accept()
                        return True
                elif is_pressed:
                    receiver.keyPressEvent(event)
                    event.accept()
                    return True
                else:
                    event.accept()
                    return True

        if event.isAutoRepeat():return True

        # ok if we got here then try keybindings function calls
        # KEYBINDING will call functions from handler file as
        # registered by KEYBIND.add_call(KEY,FUNCTION) above
        return KEYBIND.manage_function_calls(self,event,is_pressed,key,shift,cntrl)

    ########################
    # callbacks from STATUS #
    ########################

    #######################
    # callbacks from form #
    #######################

    #####################
    # general functions #
    #####################

    # keyboard jogging from key binding calls
    # double the rate if fast is true 
    def kb_jog(self, state, joint, direction, fast = False, linear = True):
        if not STATUS.is_man_mode() or not STATUS.machine_is_on():
            return
        if linear:
            distance = STATUS.get_jog_increment()
            rate = STATUS.get_jograte()/60
        else:
            distance = STATUS.get_jog_increment_angular()
            rate = STATUS.get_jograte_angular()/60
        if state:
            if fast:
                rate = rate * 2
            ACTION.JOG(joint, direction, rate, distance)
        else:
            ACTION.JOG(joint, 0, 0, 0)

    #####################
    # KEY BINDING CALLS #
    #####################

    # Machine control
    def on_keycall_ESTOP(self,event,state,shift,cntrl):
        if state:
            ACTION.SET_ESTOP_STATE(STATUS.estop_is_clear())
    def on_keycall_POWER(self,event,state,shift,cntrl):
        if state:
            ACTION.SET_MACHINE_STATE(not STATUS.machine_is_on())
    def on_keycall_HOME(self,event,state,shift,cntrl):
        if state:
            if STATUS.is_all_homed():
                ACTION.SET_MACHINE_UNHOMED(-1)
            else:
                ACTION.SET_MACHINE_HOMING(-1)
    def on_keycall_ABORT(self,event,state,shift,cntrl):
        if state:
            if STATUS.stat.interp_state == linuxcnc.INTERP_IDLE:
                self.w.close()
            else:
                self.cmnd.abort()
    def on_keycall_F12(self,event,state,shift,cntrl):
        if state:
            STYLEEDITOR.load_dialog()

    # Linear Jogging
    def on_keycall_XPOS(self,event,state,shift,cntrl):
        self.kb_jog(state, 0, 1, shift)

    def on_keycall_XNEG(self,event,state,shift,cntrl):
        self.kb_jog(state, 0, -1, shift)

    def on_keycall_YPOS(self,event,state,shift,cntrl):
        self.kb_jog(state, 1, 1, shift)

    def on_keycall_YNEG(self,event,state,shift,cntrl):
        self.kb_jog(state, 1, -1, shift)

    def on_keycall_ZPOS(self,event,state,shift,cntrl):
        self.kb_jog(state, 2, 1, shift)

    def on_keycall_ZNEG(self,event,state,shift,cntrl):
        self.kb_jog(state, 2, -1, shift)

    def on_keycall_APOS(self,event,state,shift,cntrl):
        pass
        #self.kb_jog(state, 3, 1, shift, False)

    def on_keycall_ANEG(self,event,state,shift,cntrl):
        pass
        # self.kb_jog(state, 3, -1, shift, linear=False)

    ###########################
    # **** closing event **** #
    ###########################

    ##############################
    # required class boiler code #
    ##############################

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, item, value):
        return setattr(self, item, value)

################################
# required handler boiler code #
################################


def get_handlers(halcomp, widgets, paths):
    return[HandlerClass(halcomp, widgets, paths)]
