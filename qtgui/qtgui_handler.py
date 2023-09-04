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
TCLPATH = os.environ['LINUXCNC_TCL_DIR']
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
        self.cmd = linuxcnc.command()
        self.stat = linuxcnc.stat()
        self.PATHS = paths
        self.last_loaded_file = None
        self.inifile = linuxcnc.ini(INIPATH)

    ##########################################
    # Special Functions called from QTSCREEN
    ##########################################

    # at this point:
    # the widgets are instantiated.
    # the HAL pins are built but HAL is not set ready
    def initialized__(self):
        KEYBIND.add_call('Key_F12','on_keycall_F12')
        self.open_file_show()
        
        # from status
        STATUS.connect("state-estop", lambda w: self.update_estate('ESTOP'))
        STATUS.connect("state-estop-reset", lambda w: self.update_estate('RESET'))
        STATUS.connect("state-on",lambda w: self.update_power('ON'))
        STATUS.connect("state-off",lambda w: self.update_power('OFF'))
        STATUS.connect('all-homed', self.all_hommed_upd)
        STATUS.connect('not-all-homed', self.not_all_hommed_upd)
        STATUS.connect('file-loaded', self.file_loaded)
        STATUS.connect('periodic', self.upd_pos)
        
        #stw main
        self.w.stw_main.setCurrentIndex(0)
        
        # bottom frame
        ## estop
        self.w.pb_bottom_estop.setCheckable(True)
        self.w.pb_bottom_estop.setChecked(False)
        self.w.pb_bottom_estop.clicked.connect(self.estop_state)
        
        ## power
        self.w.pb_bottom_pwr.setEnabled(False)
        self.w.pb_bottom_pwr.setCheckable(True)
        self.w.pb_bottom_pwr.setChecked(False)
        self.w.pb_bottom_pwr.clicked.connect(self.pwr_state)
        
        ## homing
        self.w.pb_bottom_homing.clicked.connect(self.homing)
        
        ## load file
        self.w.pb_bottom_programm_load.setCheckable(True)
        self.w.pb_bottom_programm_load.toggled.connect(self.load_file_dialog)
        
        ## edit file
        self.w.pb_bottom_programm_edit.clicked.connect(self.file_edit)
        
        ## reload file
        ## TODO сделать проверку загруженного файла и по его наличию назначить
        ## будет ли включена кнопка перезагрузки 
        self.w.pb_bottom_programm_reload.setEnabled(False)
        self.w.pb_bottom_programm_reload.clicked.connect(self.file_reload)
        
        ## programm run
        self.w.pb_bottom_programm_run.clicked.connect(self.programm_run)
        
        ## programm pause
        self.w.pb_bottom_programm_pause.setEnabled(False)
        self.w.pb_bottom_programm_pause.clicked.connect(self.programm_pause)
        
        ## programm abort
        self.w.pb_bottom_programm_abort.setEnabled(False)
        self.w.pb_bottom_programm_abort.clicked.connect(self.programm_abort)
        
        ## MDI
        self.w.stw_gcode.setCurrentIndex(0)
        self.w.pb_bottom_mdi.setCheckable(True)
        self.w.pb_bottom_mdi.setChecked(False)
        self.w.pb_bottom_mdi.toggled.connect(self.mdi_input)
        
        ## settings
        self.w.pb_bottom_settings.setCheckable(True)
        self.w.pb_bottom_settings.setChecked(False)
        self.w.pb_bottom_settings.toggled.connect(self.settings_page_open)
    
        # view frame
        self.start_view = self.inifile.find('DISPLAY', 'START_VIEW')
        self.view_list = ['p', 'z', 'z2']
        self.current_view = 0
        if self.start_view is not None:
            for i in self.view_list:
                if i == self.start_view:
                    self.w.cb_view_select.setCurrentIndex(self.current_view)
                    self.w.gcodegraphics.set_view(i)
                else:
                    self.current_view += 1
                    
        self.w.cb_view_select.currentIndexChanged.connect(self.change_view)
        self.w.pb_view_full.setCheckable(True)
        self.w.pb_view_full.toggled.connect(self.view_fullscreen)
        self.w.pb_view_1.clicked.connect(lambda: self.view_pb_actions('zoom-in'))
        self.w.pb_view_2.clicked.connect(lambda: self.view_pb_actions('zoom-out'))
        self.w.pb_view_3.clicked.connect(lambda: self.view_pb_actions('clear'))
        
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
        
        # Settings
        self.w.pb_settings_halshow.clicked.connect(lambda: self.run_app('halshow'))
        self.w.pb_settings_halmeter.clicked.connect(lambda: self.run_app('halmeter'))
        self.w.pb_settings_halscope.clicked.connect(lambda: self.run_app('halscope'))
        self.w.pb_settings_halstatus.clicked.connect(lambda: self.run_app('status'))
        self.w.pb_settings_halcalibration.clicked.connect(lambda: self.run_app('calibration'))
        
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
    
    def upd_pos(self, data):
        self.stat.poll()
        pos = self.stat.joint_position
        offset = self.stat.g92_offset
        join_0 = pos[0] - offset[0]
        join_1 = pos[1] - offset[1]
        self.w.lbl_xpos.setText(f'{round(join_0, 2)}')
        self.w.lbl_ypos.setText(f'{round(join_1, 2)}')
        self.w.lbl_vel_val.setText(f'{round(self.stat.current_vel, 0)}')
    
    def change_main( self, state):
        if state:
            self.w.stw_main.setCurrentIndex(1)
        else:
            self.w.stw_main.setCurrentIndex(0)
            
    def change_view(self, cur_index):
        self.w.gcodegraphics.set_view(self.view_list[cur_index])
        self.current_view = cur_index
        
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
            
    def update_estate(self, estatus):
        if estatus == 'RESET':
            self.w.pb_bottom_estop.setChecked(True)
            self.w.pb_bottom_pwr.setEnabled(True)
        else:
            self.w.pb_bottom_estop.setChecked(False)
            self.w.pb_bottom_pwr.setEnabled(False)
        
    def update_power(self, pstatus):
        if pstatus == 'ON':
            self.w.pb_bottom_pwr.setChecked(True)
            self.w.pb_bottom_homing.setEnabled(True)
        else:
            self.w.pb_bottom_pwr.setChecked(False)
            self.w.pb_bottom_homing.setEnabled(False)
        
    def all_hommed_upd(self, obj):
        self.w.pb_bottom_programm_run.setEnabled(True)
        self.w.pb_bottom_mdi.setEnabled(True)
        self.w.stw_workpiece.setEnabled(True)
        
    def not_all_hommed_upd(self, obj, list):
        self.w.pb_bottom_programm_run.setEnabled(False)
        self.w.pb_bottom_mdi.setEnabled(False)
        self.w.stw_workpiece.setEnabled(False)
    
    def homing(self):
        if STATUS.is_all_homed():
            ACTION.SET_MACHINE_UNHOMED(-1)
        else:
            ACTION.SET_MACHINE_HOMING(-1)
        view = self.w.gcodegraphics.getview()
        self.w.gcodegraphics.set_view(view)
        self.w.gcodegraphics.updateGL()
        
    def file_loaded(self, obj, filename):
        self.w.lbl_signal_0.setText(filename)
        self.last_loaded_file = filename
        if filename is not None:
            self.w.stw_main.setCurrentIndex(0)
            self.w.pb_bottom_programm_reload.setEnabled(True)
        
    def file_edit(self):
        if self.last_loaded_file:
            editor = self.inifile.find('DISPLAY', 'EDITOR')
            edit_command = f'{editor} {self.last_loaded_file} &'
            os.popen(edit_command)
        
            
    def file_reload(self):
        if self.last_loaded_file is not None:
            ACTION.OPEN_PROGRAM(self.last_loaded_file)
                    
    def programm_run(self):
        self.w.pb_bottom_programm_run.setEnabled(False)
        self.w.pb_bottom_programm_rfl.setEnabled(False)
        self.w.pb_bottom_programm_pause.setEnabled(True)
        self.w.pb_bottom_programm_abort.setEnabled(True)
        ACTION.RUN(0)
            
    def programm_pause(self):
        if not STATUS.stat.paused:
            self.cmd.auto(linuxcnc.AUTO_PAUSE)
            self.w.pb_bottom_programm_pause.setChecked(True)
        else:
            LOG.debug('resume')
            self.cmd.auto(linuxcnc.AUTO_RESUME)
            self.w.pb_bottom_programm_pause.setChecked(False)
            
    def programm_abort(self):
        self.cmd.abort()
        self.cmd.wait_complete()
        self.cmd.mode(linuxcnc.MODE_MANUAL)
        self.w.pb_bottom_programm_run.setEnabled(True)
        self.w.pb_bottom_programm_rfl.setEnabled(True)
        self.w.pb_bottom_programm_pause.setEnabled(False)
        self.w.pb_bottom_programm_abort.setEnabled(False)
        
    def mdi_input(self, state):
        if state:
            self.w.stw_gcode.setCurrentIndex(1)
        else:
            self.w.stw_gcode.setCurrentIndex(0)
            
    def settings_page_open(self, state):
        if state:
            self.w.stw_main.setCurrentIndex(2)
        else:
            self.w.stw_main.setCurrentIndex(0)
            

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
            
    # homing
    def stw_workpiece_index(self, index):
        self.w.stw_workpiece.setCurrentIndex(index)
        
    def mdi_command(self, mdi):
        self.cmd.mode(linuxcnc.MODE_MDI)
        self.cmd.wait_complete()
        self.cmd.mdi('%s' % mdi)
        
    def run_app(self, app):
        if app == 'calibration':
            os.popen("tclsh %s/bin/emccalib.tcl -- -ini %s > /dev/null &" % (TCLPATH, INIPATH), "w")
        elif app == 'status':
            os.popen("linuxcnctop  > /dev/null &", "w")   
        else:
            process = ['halshow', 'halscope', 'halmeter', ]
            for i in process:
                if i == app:
                    os.popen('/usr/bin/%s' % i)
            

    #####################
    # general functions #
    #####################
    
    def open_file_show(self):
        self.stat.poll()
        conf_path = '/'.join(self.stat.ini_filename.split('/')[:-1])
        open_file_from_ini = self.inifile.find('DISPLAY', 'OPEN_FILE')
        if open_file_from_ini is not None:
            open_file = open_file_from_ini[1:]
            open_file = conf_path + open_file
            ACTION.OPEN_PROGRAM(open_file)

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
            self.homing()
            
    def on_keycall_ABORT(self,event,state,shift,cntrl):
        if state:
            self.programm_abort()
            
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
