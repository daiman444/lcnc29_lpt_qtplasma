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
from qtvcp.core import Status, Action

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
        self.PATHS = paths
        

    ##########################################
    # Special Functions called from QTSCREEN
    ##########################################

    # at this point:
    # the widgets are instantiated.
    # the HAL pins are built but HAL is not set ready
    def initialized__(self):
        KEYBIND.add_call('Key_F12','on_keycall_F12')
    
        self.w.cb_view_select.setCurrentIndex(1)
        self.w.cb_view_select.currentIndexChanged.connect(self.change_view)
        self.w.pb_view_1.clicked.connect(lambda: self.view_pb_actions('zoom-in'))
        self.w.pb_view_2.clicked.connect(lambda: self.view_pb_actions('zoom-out'))
        self.w.pb_view_3.clicked.connect(lambda: self.view_pb_actions('clear'))
        self.w.pb_view_4.setCheckable(True)
        self.w.pb_view_4.setChecked(True)
        self.w.pb_view_4.toggled.connect(self.overlay_state)
        
        self.w.stw_main.setCurrentIndex(0)
        self.w.stw_homing.setCurrentIndex(0)
        
        self.frame_4_buttons = ['homing', 'workpiece', 'tests']
        
        for i in self.frame_4_buttons:
            self.w['pb_' + i].setCheckable(True)
        
        
        self.w.pb_bottom_10.setCheckable(True)
        self.w.pb_bottom_10.toggled.connect(self.change_main)
        
        #self.w.cb_window.currentIndexChanged.connect(self.on_combobox_changed)
        self.w.fr_left.close()
        self.w.fr_right.close()
        
        self.w.pb_view_full.setCheckable(True)
        self.w.pb_view_full.toggled.connect(self.view_fullscreen)
        
        
        #STATUS.connect('periodic', lambda w: self.gui_update())
 


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
            

    #######################
    # callbacks from form #
    #######################
    def on_combobox_changed(self, index):
        if index == 1:
            self.w.mainwindow.showMinimized()
            
    def view_fullscreen(self, state):
        if state:
            self.w.fr_view.setMaximumWidth(3000)
            self.w.frame_2.close()
        else:
            fr_view_width = int(self.w.stw.width() / 2)
            self.w.fr_view.setMaximumWidth(fr_view_width)
            self.w.frame_2.show()
            g_code_view_width = int(self.w.frame_3.width() / 2)
            self.w.gcode_display.setMinimumWidth(g_code_view_width)

        
            
    
            
        
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
