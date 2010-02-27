#    Back In Time
#    Copyright (C) 2008-2009 Oprea Dan, Bart de Koning, Richard Bailey
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


import os
import os.path
import sys
import pygtk
pygtk.require("2.0")
import gtk
import gnomevfs
import gobject
import datetime
import gettext

import config
import tools
import clipboardtools 
import messagebox
import gnometools
import hashlib


_=gettext.gettext

def _get_md5sum_from_path(path):
    try:
        path = open(path, 'r')
        md5sum = hashlib.md5(path.read())
    except IOError:
        return False  
    return md5sum.hexdigest()


class SnapshotsDialog(object):

    def __init__( self, snapshots, parent, path, snapshots_list, current_snapshot_id, icon_name ):
        self.snapshots = snapshots
        self.config = snapshots.config
        
        builder = gtk.Builder()
        self.builder = builder

        glade_file = os.path.join(self.config.get_app_path(), 'gnome',
                'snapshotsdialog.glade')

        builder.add_from_file(glade_file)

        self.path = None
        self.icon_name = None

        self.dialog = self.builder.get_object( 'SnapshotsDialog' )
        self.dialog.set_transient_for( parent )

        signals = { 
            'on_list_snapshots_cursor_changed' : self.on_list_snapshots_cursor_changed,
            'on_list_snapshots_row_activated' : self.on_list_snapshots_row_activated,
            'on_list_snapshots_popup_menu' : self.on_list_snapshots_popup_menu,
            'on_list_snapshots_button_press_event': self.on_list_snapshots_button_press_event,
            'on_list_snapshots_drag_data_get': self.on_list_snapshots_drag_data_get,
            'on_btn_diff_with_clicked' : self.on_btn_diff_with_clicked,
            'on_btn_copy_snapshot_clicked' : self.on_btn_copy_snapshot_clicked,
            'on_btn_restore_snapshot_clicked' : self.on_btn_restore_snapshot_clicked,
            'on_check_only_different_toggled' : self.on_check_only_different_toggled
            }

        #path
        self.edit_path = self.builder.get_object( 'edit_path' )

        #diff
        self.edit_diff_cmd = self.builder.get_object( 'edit_diff_cmd' )
        self.edit_diff_cmd_params = self.builder.get_object( 'edit_diff_cmd_params' )

        diff_cmd = self.config.get_str_value( 'gnome.diff.cmd', 'meld' )
        diff_cmd_params = self.config.get_str_value( 'gnome.diff.params', '%1 %2' )

        self.edit_diff_cmd.set_text( diff_cmd )
        self.edit_diff_cmd_params.set_text( diff_cmd_params )

        #setup backup folders
        self.list_snapshots = self.builder.get_object( 'list_snapshots' )
        self.list_snapshots.drag_source_set( gtk.gdk.BUTTON1_MASK | gtk.gdk.BUTTON3_MASK, gtk.target_list_add_uri_targets(), gtk.gdk.ACTION_COPY )

        ### connect callbacks to widgets signals.
        builder.connect_signals(signals)
        
        text_renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn( _('Snapshots') )
        column.pack_end( text_renderer, True )
        column.add_attribute( text_renderer, 'markup', 0 )
        column.set_sort_column_id( 0 )
        self.list_snapshots.append_column( column )

        #display name, snapshot_id
        self.store_snapshots = gtk.ListStore( str, str )
        self.list_snapshots.set_model( self.store_snapshots )

        self.store_snapshots.set_sort_column_id( 0, gtk.SORT_DESCENDING )

        #setup diff with combo
        self.combo_diff_with = self.builder.get_object( 'combo_diff_with' )
        text_renderer = gtk.CellRendererText()
        self.combo_diff_with.pack_start( text_renderer, True )
        self.combo_diff_with.add_attribute( text_renderer, 'markup', 0 )
        self.combo_diff_with.set_model( self.store_snapshots ) #use the same store

        #UPDATE
        self.list_only_different_snapshots = False
        self.current_snapshot_id, self.snapshots_list = current_snapshot_id, snapshots_list
        self.path = path
        self.icon_name = icon_name
        self.update_snapshots( current_snapshot_id, snapshots_list )

    def update_toolbar( self ):
        if len( self.store_snapshots ) <= 0:
            self.builder.get_object( 'btn_copy_snapshot' ).set_sensitive( False )
            self.builder.get_object( 'btn_restore_snapshot' ).set_sensitive( False )
        else:
            self.builder.get_object( 'btn_copy_snapshot' ).set_sensitive( True )

            iter = self.list_snapshots.get_selection().get_selected()[1]
            if iter is None:
                self.builder.get_object( 'btn_restore_snapshot' ).set_sensitive( False )
            else:
                path = self.store_snapshots.get_value( iter, 1 )
                self.builder.get_object( 'btn_restore_snapshot' ).set_sensitive( len( path ) > 1 )

    def on_btn_restore_snapshot_clicked( self, button ):
        iter = self.list_snapshots.get_selection().get_selected()[1]
        if not iter is None:
            button.set_sensitive( False )
            gnometools.run_gtk_update_loop()
            self.snapshots.restore( self.store_snapshots.get_value( iter, 1 ), self.path )
            button.set_sensitive( True )

    def on_btn_copy_snapshot_clicked( self, button ):
        iter = self.list_snapshots.get_selection().get_selected()[1]
        if not iter is None:
            path = self.snapshots.get_snapshot_path_to( self.store_snapshots.get_value( iter, 1 ), self.path )
            clipboardtools.clipboard_copy_path( path )
 
    def on_list_snapshots_drag_data_get( self, widget, drag_context, selection_data, info, timestamp, user_param1 = None ):
        iter = self.list_snapshots.get_selection().get_selected()[1]
        if not iter is None:
            path = self.store_snapshots.get_value( iter, 2 )
            path = gnomevfs.escape_path_string(path)
            selection_data.set_uris( [ 'file://' + path ] )

    def on_list_snapshots_cursor_changed( self, list ):
        self.update_toolbar()

    def on_list_snapshots_button_press_event( self, list, event ):
        if event.button != 3:
            return

        if len( self.store_snapshots ) <= 0:
            return

        path = self.list_snapshots.get_path_at_pos( int( event.x ), int( event.y ) )
        if path is None:
            return
        path = path[0]
    
        self.list_snapshots.get_selection().select_path( path )
        self.update_toolbar()
        self.show_popup_menu( self.list_snapshots, event.button, event.time )

    def on_list_snapshots_popup_menu( self, list ):
        self.showPopupMenu( list, 1, gtk.get_current_event_time() )

    def show_popup_menu( self, list, button, time ):
        iter = list.get_selection().get_selected()[1]
        if iter is None:
            return

        #print "popup-menu"
        self.popup_menu = gtk.Menu()

        menu_item = gtk.ImageMenuItem( 'backintime.open' )
        menu_item.set_image( gtk.image_new_from_icon_name( self.icon_name, gtk.ICON_SIZE_MENU ) )
        menu_item.connect( 'activate', self.on_list_snapshots_open_item )
        self.popup_menu.append( menu_item )

        self.popup_menu.append( gtk.SeparatorMenuItem() )

        menu_item = gtk.ImageMenuItem( 'backintime.copy' )
        menu_item.set_image( gtk.image_new_from_stock( gtk.STOCK_COPY, gtk.ICON_SIZE_MENU ) )
        menu_item.connect( 'activate', self.on_list_snapshots_copy_item )
        self.popup_menu.append( menu_item )

        menu_item = gtk.ImageMenuItem( gtk.STOCK_JUMP_TO )
        menu_item.connect( 'activate', self.on_list_snapshots_jumpto_item )
        self.popup_menu.append( menu_item )

        path = self.store_snapshots.get_value( iter, 1 )
        if len( path ) > 1:
            menu_item = gtk.ImageMenuItem( 'backintime.restore' )
            menu_item.set_image( gtk.image_new_from_stock( gtk.STOCK_UNDELETE, gtk.ICON_SIZE_MENU ) )
            menu_item.connect( 'activate', self.on_list_snapshots_restore_item )
            self.popup_menu.append( menu_item )

        self.popup_menu.append( gtk.SeparatorMenuItem() )

        menu_item = gtk.ImageMenuItem( 'backintime.diff' )
        #menu_item.set_image( gtk.image_new_from_stock( gtk.STOCK_COPY, gtk.ICON_SIZE_MENU ) )
        menu_item.connect( 'activate', self.on_list_snapshots_diff_item )
        self.popup_menu.append( menu_item )

        self.popup_menu.show_all()
        self.popup_menu.popup( None, None, None, button, time )

    def on_list_snapshots_diff_item( self, widget, data = None ):
        self.on_btn_diff_with_clicked( self.builder.get_object( 'btn_diff_with' ) )

    def on_list_snapshots_jumpto_item( self, widget, data = None ):
        self.dialog.response( gtk.RESPONSE_OK )

    def on_list_snapshots_open_item( self, widget, data = None ):
        self.open_item()

    def on_list_snapshots_restore_item( self, widget, data = None ):
        self.on_btn_restore_snapshot_clicked( self.builder.get_object( 'btn_restore_snapshot' ) )

    def on_list_snapshots_copy_item( self, widget, data = None ):
        self.on_btn_copy_snapshot_clicked( self.builder.get_object( 'btn_copy_snapshot' ) )

    def on_btn_diff_with_clicked( self, button ):
        if len( self.store_snapshots ) < 1:
            return

        #get path from the list
        iter = self.list_snapshots.get_selection().get_selected()[1]
        if iter is None:
            return
        path1 = self.snapshots.get_snapshot_path_to( self.store_snapshots.get_value( iter, 1 ), self.path )

        #get path from the combo
        path2 = self.snapshots.get_snapshot_path_to( self.store_snapshots.get_value( self.combo_diff_with.get_active_iter(), 1 ), self.path )

        #check if the 2 paths are different
        if path1 == path2:
            messagebox.show_error( self.dialog, self.config, _('You can\'t compare a snapshot to itself') )
            return

        diff_cmd = self.edit_diff_cmd.get_text()
        diff_cmd_params = self.edit_diff_cmd_params.get_text()

        if not tools.check_command( diff_cmd ):
            messagebox.show_error( self.dialog, self.config, _('Command not found: %s') % diff_cmd )
            return

        params = diff_cmd_params
        params = params.replace( '%1', "\"%s\"" % path1 )
        params = params.replace( '%2', "\"%s\"" % path2 )

        cmd = diff_cmd + ' ' + params + ' &'
        os.system( cmd  )

        #check if the command changed
        old_diff_cmd = self.config.get_str_value( 'gnome.diff.cmd', 'meld' )
        old_diff_cmd_params = self.config.get_str_value( 'gnome.diff.params', '%1 %2' )
        if diff_cmd != old_diff_cmd or diff_cmd_params != old_diff_cmd_params:
            self.config.set_str_value( 'gnome.diff.cmd', diff_cmd )
            self.config.set_str_value( 'gnome.diff.params', diff_cmd_params )
            self.config.save()

    def on_check_only_different_toggled( self, widget, data = None ):
        self.list_only_different_snapshots = not self.list_only_different_snapshots
        self.update_snapshots(self.current_snapshot_id, self.snapshots_list )
        

    def update_snapshots( self, current_snapshot_id, snapshots_list ):
        self.edit_path.set_text( self.path )

        #fill snapshots
        self.store_snapshots.clear()
    
        path = self.snapshots.get_snapshot_path_to( current_snapshot_id, self.path )    
        isdir = os.path.isdir( path )

        counter = 0
        index_combo_diff_with = 0
        
        #add now
        md5set = set()
        path = self.path
        if os.path.lexists( path ):
            if os.path.isdir( path ) == isdir:
                md5set.add(_get_md5sum_from_path(path))
                self.store_snapshots.append( [ gnometools.get_snapshot_display_markup( self.snapshots, '/' ), '/' ] )
                if '/' == current_snapshot_id:
                    indexComboDiffWith = counter
                counter += 1
                
        #add snapshots
        for snapshot in snapshots_list:
            path = self.snapshots.get_snapshot_path_to( snapshot, self.path )
            if os.path.lexists( path ):
                if os.path.isdir( path ) == isdir:
                    md5sum = _get_md5sum_from_path(path)
                    if md5sum not in md5set or not self.list_only_different_snapshots:
                        md5set.add(md5sum)
                        self.store_snapshots.append( [ gnometools.get_snapshot_display_markup( self.snapshots, snapshot), snapshot ] )
                        if snapshot == current_snapshot_id:
                            index_combo_diff_with = counter
                        counter += 1

        #select first item
        if len( self.store_snapshots ) > 0:
            iter = self.store_snapshots.get_iter_first()
            if not iter is None:
                self.list_snapshots.get_selection().select_iter( iter )
            self.combo_diff_with.set_active( index_combo_diff_with )
    
            self.builder.get_object( 'btn_diff_with' ).set_sensitive( True )
            self.combo_diff_with.set_sensitive( True )
        else:
            self.builder.get_object( 'btn_diff_with' ).set_sensitive( False )
            self.combo_diff_with.set_sensitive( False )

        self.list_snapshots.grab_focus()
        self.update_toolbar()

    def on_list_snapshots_row_activated( self, list, path, column ):
        self.open_item()

    def open_item( self ):
		iter = self.list_snapshots.get_selection().get_selected()[1]
		if iter is None:
			return
        
		path = self.snapshots.get_snapshot_path_to( self.store_snapshots.get_value( iter, 1 ), self.path )
		if not os.path.exists( path ):
			return

		cmd = "gnome-open \"%s\" &" % path
		os.system( cmd )

    def run( self ):
        snapshot_id = None
        while True:
            ret_val = self.dialog.run()
            
            if gtk.RESPONSE_OK == ret_val: #go to
                iter = self.list_snapshots.get_selection().get_selected()[1]
                if not iter is None:
                    snapshot_id = self.store_snapshots.get_value( iter, 1 )
                break
            else:
                #cancel, close ...
                break

        self.dialog.destroy()
        return snapshot_id

