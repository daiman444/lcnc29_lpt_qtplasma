############################
# **** IMPORT SECTION **** #
############################
import sys
import os
import linuxcnc
import math

from PyQt5 import QtCore, QtWidgets

from qtvcp.widgets.mdi_line import MDILine as MDI_WIDGET
from qtvcp.widgets.gcode_editor import GcodeEditor as GCODE
from qtvcp.widgets.stylesheeteditor import  StyleSheetEditor as SSE
from qtvcp.lib.keybindings import Keylookup
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
INIPATH = os.environ.get('INI_FILE_NAME', '/dev/null')
###################################
# **** HANDLER CLASS SECTION **** #
###################################

class HandlerClass:

    ########################
    # **** INITIALIZE **** #
    ########################
    # widgets allows access to  widgets from the qtvcp files
    # at this point the widgets and hal pins are not instantiated
    def __init__(self, halcomp,widgets,paths):
        self.hal = halcomp
        self.w = widgets
        self.PATHS = paths
        self.stat = linuxcnc.stat()
        self.cmd = linuxcnc.command()
        self.inifile = linuxcnc.ini(INIPATH)
        self.coordinates = self.inifile.find('TRAJ', 'COORDINATES')
        self.coord_labels = ('lbl_axis_0', 'lbl_axis_1', 'lbl_axis_2', 'lbl_axis_3',)
        self.coord_dros = ('dro_label_0', 'dro_label_1', 'dro_label_2', 'dro_label_3', )
        self.coord_push_buttons = ('pb_jog_0_plus', 'pb_jog_1_plus', 'pb_jog_2_plus', 'pb_jog_3_plus',
                                   'pb_jog_0_minus', 'pb_jog_1_minus', 'pb_jog_2_minus', 'pb_jog_3_minus',
                                   )
        self.mdi_pbuttons = ('pb_g0x0y0_zsafe', 'pb_g92x0y0z0', 'pb_g92x0',
                             'pb_g92y0', 'pb_g92z0', 'pb_g53xmax_ymax',
                             )

        self.counter = 0




    ##########################################
    # Special Functions called from QTSCREEN
    ##########################################

    # at this point:
    # the widgets are instantiated.
    # the HAL pins are built but HAL is not set ready
    def initialized__(self):
        KEYBIND.add_call('Key_F12','on_keycall_F12')

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

        # MDI commands for coordinates

        for i in self.mdi_pbuttons:
            command = i.replace('pb_', '')
            self.w[i].clicked.connect(lambda w, cmd=command: self.mdi_commands(cmd))




        STATUS.connect('periodic', self.some_def)
        STATUS.connect('state-estop', lambda w: self.estop_state(True))
        STATUS.connect('motion-mode-changed', self.motion_mode)
        STATUS.connect('current-position', self.current_pos)

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
        STATUS.stat.poll()
        if isinstance(state, bool) and linuxcnc.MODE_MANUAL:
            if state:
                self.cmd.teleop_enable(False)
                ACTION.SET_MACHINE_HOMING(-1)
                self.cmd.wait_complete()
                self.cmd.teleop_enable(True)
                self.cmd.wait_complete()
            else:
                self.cmd.teleop_enable(False)
                ACTION.SET_MACHINE_UNHOMED(-1)
                self.cmd.wait_complete()
        self.stat.poll()

    def motion_mode(self, obj, mode):
        if mode == 1:
            self.show_joints()
        if mode == 3:
            self.show_axes()

# TODO exlude dro_labels and make a methods to display coordinates in labels
    def show_joints(self):
        for i in range(0, 4):
            self.w['lbl_axis_%s' % i].close()
            self.w['dro_label_%s' % i].close()
            self.w['pb_jog_%s_plus' % i].close()
            self.w['pb_jog_%s_minus' % i].close()
            if i in range(0, len(self.coordinates)):
                self.w['lbl_axis_%s' % i].show()
                self.w['lbl_axis_%s' % i].setText('%s'%i)
                self.w['dro_label_%s' % i].show()
                self.w['pb_jog_%s_plus' % i].show()
                self.w['pb_jog_%s_minus' % i].show()

    def show_axes(self):
        for i in range(0, 4):
            self.w['lbl_axis_%s' % i].close()
            self.w['dro_label_%s' % i].close()
            self.w['pb_jog_%s_plus' % i].close()
            self.w['pb_jog_%s_minus' % i].close()
            if i in range(0, len(set(self.coordinates))):
                axis_name = "XYZ"[i]
                self.w['lbl_axis_%s' % i].show()
                self.w['lbl_axis_%s' % i].setText('%s'% axis_name)
                self.w['dro_label_%s' % i].show()
                self.w['pb_jog_%s_plus' % i].show()
                self.w['pb_jog_%s_minus' % i].show()

    def some_def(self, w, data=None):
        pass

    def current_pos(self, w, pos1, pos2, pos3, pos4):
        self.w.label_2.setText('%.2f, %.2f, %.2f, %.2f' % (pos1[0], pos1[1], pos1[2], pos1[3] ))
        self.w.label_3.setText('%.2f, %.2f, %.2f, %.2f' % (pos2[0], pos2[1], pos2[2], pos2[3] ))
        #self.w.label_4.setText('%.2f, %.2f, %.2f, %.2f' % (pos3[0], pos3[1], pos3[2], pos3[3] ))
        #self.w.label_5.setText('%.2f, %.2f, %.2f, %.2f' % (pos4[0], pos4[1], pos4[2], pos4[3] ))

    def mdi_commands(self, mdi):
        complete_time = 10
        if mdi == 'g53xmax_ymax':
            y_coord = self.inifile.find('AXIS_Y', 'MAX_LIMIT')
            x_max = self.inifile.find('AXIS_X', 'MAX_LIMIT')
            x_min = self.inifile.find('AXIS_X', 'MIN_LIMIT')
            if abs(float(x_min)) > float(x_max):
                x_coord = x_min
            else:
                x_coord = x_max
            mdi = 'g53g0 x %s y %s' % (x_coord, y_coord)
            complete_time = 180
        if mdi == 'g0x0y0_zsafe':
            safe = self.inifile.find('UD_PARAMS', 'SAFE_Z')
            mdi = mdi.replace('_zsafe', 'z %s' % safe)
            complete_time = 180
        self.w.label_5.setText('%s' % mdi)
        self.cmd.mode(linuxcnc.MODE_MDI)
        #self.cmd.mdi(mdi)
        ACTION.CALL_MDI(mdi)
        # TODO deal with wait_complete
        self.cmd.wait_complete(complete_time)
        self.cmd.mode(linuxcnc.MODE_MANUAL)



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
        #self.kb_jog(state, 3, -1, shift, linear=False)

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

def get_handlers(halcomp,widgets,paths):
     return [HandlerClass(halcomp,widgets,paths)]
