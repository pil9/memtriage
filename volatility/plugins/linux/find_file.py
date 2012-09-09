# Volatility
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details. 
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA 

"""
@author:       Andrew Case
@license:      GNU General Public License 2.0 or later
@contact:      atcuno@gmail.com
@organization:
"""

import sys, os
import volatility.obj as obj
import volatility.plugins.linux.common as linux_common
import volatility.plugins.linux.mount as linux_mount
import volatility.plugins.linux.flags as linux_flags
import volatility.debug as debug
import volatility.utils as utils

class linux_find_file(linux_common.AbstractLinuxCommand):
    '''Recovers tmpfs filesystems from memory'''

    def __init__(self, config, *args):
        linux_common.AbstractLinuxCommand.__init__(self, config, *args)
        self._config.add_option('FIND',  short_option = 'F', default = None, help = 'file (path) to find', action = 'store', type = 'str')
        self._config.add_option('INODE', short_option = 'i', default = None, help = 'inode to write to disk', action = 'store', type = 'int')
        self._config.add_option('OUTFILE', short_option = 'O', default = None, help = 'output file path', action = 'store', type = 'str')

    def walk_sb(self, dentry, find_file, recursive = 0, parent = ""):

        ret = None

        for dentry in dentry.d_subdirs.list_of_type("dentry", "d_u"):

            if not dentry.d_name.name.is_valid():
                continue

            inode = dentry.d_inode
            name  = dentry.d_name.name.dereference_as("String", length = 255)

            # do not use os.path.join
            # this allows us to have consistent paths from the user
            new_file = parent + "/" + name
            
            if new_file == find_file:
                ret = dentry                
                break

            if inode:
                               
                if linux_common.S_ISDIR(inode.i_mode):
                    # since the directory may already exist
                    ret = self.walk_sb(dentry, find_file, 1, new_file)
                    if ret:
                        break
    
        return ret
                    
    def get_sbs(self):
        ret = []
        mnts = linux_mount.linux_mount(self._config).calculate()

        for (sb, _dev_name, path, fstype, _rr, _mnt_string) in linux_mount.linux_mount(self._config).parse_mnt(mnts):
            ret.append((sb, path))

        return ret

    def walk_sbs(self, find_file):
        ret = None
        sbs = self.get_sbs()

        first_dir = "/".join(find_file.split("/")[:2])
        
        for (sb, path) in sbs:

            if len(path) > 1 and not path.startswith(first_dir):
                continue

            ret = self.walk_sb(sb.s_root, find_file)
            
            if ret:
                break

        return ret

    def calculate(self):
        find_file  = self._config.FIND
        inode_addr = self._config.inode        
        outfile    = self._config.outfile

        if find_file and len(find_file):

            wanted_dentry = self.walk_sbs(find_file)

            if wanted_dentry:
                yield wanted_dentry

        elif inode_addr and inode_addr > 0 and outfile and len(outfile) > 0:
        
            inode = obj.Object("inode", offset=inode_addr, vm=self.addr_space)
            
            contents = linux_common.get_file_contents(self, inode)

            f = open(outfile, "wb")
            f.write(contents)
            f.close()

        else:
            debug.error("Incorrect command line parameters given.")

    def render_text(self, outfd, data):

        shown_header = 0

        for dentry in data:

            if not shown_header:
                self.table_header(outfd, [("Inode Number", "16"), ("Inode", "[addr]")])
                shown_header = 1

            inode     = dentry.d_inode
            inode_num = inode.i_ino

            self.table_row(outfd, inode_num, inode)
            

