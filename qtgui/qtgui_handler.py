############################
# **** IMPORT SECTION **** #
############################
import sys
import os
import linuxcnc

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
        self.cmd = linuxcnc.command()
        self.stat = linuxcnc.stat()
        self.PATHS = paths
        
        self.last_loaded_file = None
        

    ##########################################
    # Special Functions called from QTSCREEN
    ##########################################

    # at this point:
    # the widgets are instantiated.
    # the HAL pins are built but HAL is not set ready
    def initialized__(self):
        KEYBIND.add_call('Key_F12','on_keycall_F12')
        # from status
        STATUS.connect("state-estop", lambda w: self.update_estate('ESTOP'))
        STATUS.connect("state-estop-reset", lambda w: self.update_estate('RESET'))
        STATUS.connect("state-on",lambda w: self.update_power('ON'))
        STATUS.connect("state-off",lambda w: self.update_power('OFF'))
        STATUS.connect('file-loaded', self.file_loaded)
        
        #stw main
        self.w.stw_main.setCurrentIndex(0)
        
        # bottom frame
        
        ## estop
        self.w.pb_bottom_0.setCheckable(True)
        self.w.pb_bottom_0.setChecked(False)
        self.w.pb_bottom_0.clicked.connect(self.estop_state)
        
        ## power
        self.w.pb_bottom_1.setEnabled(False)
        self.w.pb_bottom_1.setCheckable(True)
        self.w.pb_bottom_1.setChecked(False)
        self.w.pb_bottom_1.clicked.connect(self.pwr_state)
        
        ## load file
        self.w.pb_bottom_2.setCheckable(True)
        self.w.pb_bottom_2.toggled.connect(self.load_file_dialog)
        
        ## reload file
        self.w.pb_bottom_3.setEnabled(False)
        self.w.pb_bottom_3.clicked.connect(self.file_reload)
        
        ## programm run
        self.w.pb_bottom_4.clicked.connect(self.programm_run)
        
        ## programm pause
        self.w.pb_bottom_6.setEnabled(False)
        self.w.pb_bottom_6.clicked.connect(self.programm_pause)
        
        ## programm abort
        self.w.pb_bottom_7.setEnabled(False)
        self.w.pb_bottom_7.clicked.connect(self.programm_abort)
    
        # view frame
        self.w.cb_view_select.setCurrentIndex(0)
        self.w.cb_view_select.currentIndexChanged.connect(self.change_view)
        self.w.pb_view_full.setCheckable(True)
        self.w.pb_view_full.toggled.connect(self.view_fullscreen)
        self.w.pb_view_1.clicked.connect(lambda: self.view_pb_actions('zoom-in'))
        self.w.pb_view_2.clicked.connect(lambda: self.view_pb_actions('zoom-out'))
        self.w.pb_view_3.clicked.connect(lambda: self.view_pb_actions('clear'))
        self.w.pb_view_4.clicked.connect(lambda: self.view_pb_actions('overlay-dro-off'))
        self.w.pb_view_5.clicked.connect(lambda: self.view_pb_actions('reload'))
        
        # homing frame
        self.w.stw_workpiece.setCurrentIndex(0)
        
        ## pb_workpiece
        self.w.pb_workpiece.setCheckable(True)
        self.w.pb_workpiece.setChecked(True)
        self.w.pb_workpiece.toggled.connect(lambda: self.stw_workpiece_index(0))
        
        ## pb_tests
        self.w.pb_tests.setCheckable(True)
        self.w.pb_tests.setChecked(False)
        self.w.pb_tests.toggled.connect(lambda: self.stw_workpiece_index(1))
        
        ### pb_x_zero
        self.w.pb_x_zero.clicked.connect(lambda: self.mdi_command('G92X0'))
        self.w.pb_y_zero.clicked.connect(lambda: self.mdi_command('G92y0'))
        self.w.pb_z_zero.clicked.connect(lambda: self.mdi_command('G92z0'))
        self.w.pb_xyz_zero.clicked.connect(lambda: self.mdi_command('G92xyz0'))
        
        
        # panels
        self.w.fr_left.close()
        self.w.fr_right.close()
        
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
    
    def change_main( self, state):
        if state:
            self.w.stw_main.setCurrentIndex(1)
        else:
            self.w.stw_main.setCurrentIndex(0)
            
    def change_view(self, cur_index):
        view_list = ['p', 'x',  'y', 'z', ]
        self.w.gcodegraphics.set_view(view_list[cur_index])
        
    def view_pb_actions(self, set_action):
        if set_action == 'reload':
            STATUS.emit('reload-display')
        else:
            ACTION.SET_GRAPHICS_VIEW(set_action)        
        
    def gui_update(self, *args):
        if self.w.pb_view_full.toggled(False):
            fr_view_width = int(self.w.stw.width() / 2)
            self.w.fr_view.setMaximumWidth(fr_view_width)
            self.w.frame_2.show()
            g_code_view_width = int(self.w.frame_3.width() / 2)
            self.w.gcode_display.setMinimumWidth(g_code_view_width)
        elif self.w.pb_view_full.toggled(True):
            self.w.fr_view.setMaximumWidth(3000)
            self.w.frame_2.close()
            
    def update_estate(self, estatus):
        if estatus == 'RESET':
            self.w.pb_bottom_0.setChecked(True)
            self.w.pb_bottom_1.setEnabled(True)
        else:
            self.w.pb_bottom_0.setChecked(False)
            self.w.pb_bottom_1.setEnabled(False)
        self.w.pb_bottom_0.setText(estatus)
        
    def update_power(self, pstatus):
        if pstatus == 'ON':
            self.w.pb_bottom_1.setChecked(True)
        else:
            self.w.pb_bottom_1.setChecked(False)
        self.w.pb_bottom_1.setText(pstatus)
    
    def file_loaded(self, obj, filename):
        self.w.lbl_signal_0.setText(filename)
        self.last_loaded_file = filename
        if filename is not None:
            self.w.stw_main.setCurrentIndex(0)
            self.w.pb_bottom_3.setEnabled(True)
            
    def file_reload(self):
        if self.last_loaded_file is not None:
            ACTION.OPEN_PROGRAM(self.last_loaded_file)
           
    def programm_run(self):
        self.w.pb_bottom_4.setEnabled(False)
        self.w.pb_bottom_5.setEnabled(False)
        self.w.pb_bottom_6.setEnabled(True)
        self.w.pb_bottom_7.setEnabled(True)
        ACTION.RUN(0)
            
    def programm_pause(self):
        if not STATUS.stat.paused:
            self.cmd.auto(linuxcnc.AUTO_PAUSE)
            self.w.pb_bottom_6.setChecked(True)
        else:
            LOG.debug('resume')
            self.cmd.auto(linuxcnc.AUTO_RESUME)
            self.w.pb_bottom_6.setChecked(False)
            
    def programm_abort(self):
        self.cmd.abort()
        self.cmd.mode(linuxcnc.MODE_MANUAL)
        self.w.pb_bottom_4.setEnabled(True)
        self.w.pb_bottom_5.setEnabled(True)
        self.w.pb_bottom_6.setEnabled(False)
        self.w.pb_bottom_7.setEnabled(False)

    #######################
    # callbacks from form #
    #######################
    # bottom frame
    
    def estop_state(self):
        self.stat.poll()
        if not self.stat.estop:
            self.cmd.state(linuxcnc.STATE_ESTOP)
        else:
            self.cmd.state(linuxcnc.STATE_ESTOP_RESET)
            
    def pwr_state(self):
        self.stat.poll()
        if not self.stat.enabled:
            self.cmd.state(linuxcnc.STATE_ON)
        else:
            self.cmd.state(linuxcnc.STATE_OFF)
    
    def load_file_dialog(self, state):
        if state:
            self.w.stw_main.setCurrentIndex(1)
        else:
            self.w.stw_main.setCurrentIndex(0)
    
    # view frame
    def view_fullscreen(self, state):
        if state:
            self.w.fr_view.setMaximumWidth(3000)
            self.w.frame_2.close()
        else:
            fr_view_width = int(self.w.stw_main.width() / 2)
            self.w.fr_view.setMaximumWidth(fr_view_width)
            self.w.frame_2.show()
            g_code_view_width = int(self.w.frame_3.width() / 2)
            self.w.gcode_display.setMinimumWidth(g_code_view_width)
            
    # stw_homing
    def stw_workpiece_index(self, index):
        self.w.stw_workpiece.setCurrentIndex(index)
        
    def mdi_command(self, mdi):
        self.cmd.mode(linuxcnc.MODE_MDI)
        self.cmd.wait_complete()
        self.cmd.mdi('%s' % mdi)

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
            self.estop_state()
        
    def on_keycall_POWER(self,event,state,shift,cntrl):
        if state:
            self.pwr_state()
        
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
