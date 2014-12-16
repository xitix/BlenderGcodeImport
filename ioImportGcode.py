# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

## blendish python ripped from fro io_import_dxf

import string
import os
import bpy
import mathutils
import math
import copy

bl_info = {
    'name': 'Import Slic3r GCode',
    'author': 'Lee Butler',
    'version': (0,1,0),
    'blender': (2, 7, 0),
    'api': 32738,
    'location': 'File > Import-Export > Gcode',
    'description': 'Import and visualize gcode files generated by Slic3r (.gcode)',
    "wiki_url": "",
    "tracker_url": "",
    'category': 'Import-Export'}

__version__ = '.'.join([str(s) for s in bl_info['version']])


class IMPORT_OT_gcode(bpy.types.Operator):
    '''Imports Reprap FDM gcode'''
    bl_idname = "import_scene.gocde"
    bl_description = 'Gcode reader, reads tool moves and animates layer build'
    bl_label = "Import gcode" +' v.'+ __version__
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"

    filepath = bpy.props.StringProperty(name="File Path", description="Filepath used for importing the GCode file", maxlen= 1024, default= "")

    def __init__(self):
        # current tool position
        self.pos = {'X':0.0, 'Y':0.0, 'Z':0.0, 'E':0.0}

        # set of accumulated points on current extrusion path
        # a set of points makes up a polyline
        self.points = []

        # set of polylines 
        self.polys = []

        # each layer is a set of polylines at a constant Z
        self.layers = []

        # set of Z elevation changes.  Most common is layer height
        self.thickness = { }
        
        self.ySquash = 0.5
        self.xOoze = 1.65


    ##### DRAW #####
    def draw(self, context):
        layout0 = self.layout

    ##### EXECUTE #####
    def execute(self, context):
        print('execute')
        self.parse(self.filepath)
        return {'FINISHED'}

    ##### INVOKE  #####
    def invoke(self, context, event):
        print('invoke')
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}

    ##### PARSE #####
    def parse(self, fileName):
        self.points = []

        #print ('---------- read ' + fileName + ' ------------')
        # get the object/curve names from the filename
        self.obName = fileName.split(os.sep)[-1]
        self.obName = self.obName.replace(".gcode", "")

        f = open(fileName)
        for line in f.readlines():
            # remove comments and leading/trailing whitespace
            line = line.split(';', 1)[0].strip()

            # skip the blank lines
            if len(line) < 1:
                continue

            # tokenize the line
            tokens = line.split()

            self.dispatch(tokens)
        f.close()
        self.newLayer(-1.0)
        
        #print ('---------- build ------------')
        #print (' %d slices' % len(self.layers) )
        #print (' deltaZ values:')
        count = 0
        radius = 0
        # find the most common inter-layer distance
        for key in sorted(self.thickness.keys()):
               #print( '  %s : %d' % (key,self.thickness[key]) )
               if self.thickness[key] > count:
                   count = self.thickness[key]
                   radius = key


        profileName = self.obName + '_profile'
        profileData = bpy.data.curves.new(profileName, type='CURVE')
        profileData.dimensions = '3D'

        profilePoly = profileData.splines.new('POLY')
        profilePoly.points.add(7)
        angRad = radius * 0.70711
        profilePoly.points[7].co = (radius * self.xOoze,  0.0,                 0.0, 1)
        profilePoly.points[6].co = (angRad* self.xOoze,  angRad* self.ySquash, 0.0, 1)
        profilePoly.points[5].co = (0.0,                 radius* self.ySquash, 0.0, 1)
        profilePoly.points[4].co = (-angRad* self.xOoze,  angRad* self.ySquash, 0.0, 1)
        profilePoly.points[3].co = (-radius* self.xOoze,  0.0,                  0.0, 1)
        profilePoly.points[2].co = (-angRad* self.xOoze,  -angRad* self.ySquash, 0.0, 1)
        profilePoly.points[1].co = (0.0,                  -radius* self.ySquash, 0.0, 1)
        profilePoly.points[0].co = (angRad* self.xOoze,  -angRad* self.ySquash, 0.0, 1)
        profilePoly.use_cyclic_u = True
        #print (dir(profilePoly))
        profileObject = bpy.data.objects.new(profileName, profileData)

        scn = bpy.context.scene
        scn.objects.link(profileObject)
        scn.objects.active = profileObject


        for layerNum,layer in enumerate(self.layers):

            layerName = self.obName + '_slice_%d' % layerNum
            curveData = bpy.data.curves.new(layerName, type='CURVE')
            curveData.dimensions = '3D'
            curveData.bevel_object = profileObject
            #print (layerName + ':')

            for poly in layer:
                pointNum = 0
                for point in poly:
                    if pointNum == 0:
                        x,y,z = point
                        oldPt = mathutils.Vector((x, y, z, 1))
                        pointNum = 1
                    else:
                        polyline = curveData.splines.new('POLY')
                        polyline.points.add(1)

                        x,y,z = point
                        newPt = mathutils.Vector((x, y, z, 1))
                        polyline.points[0].co = oldPt
                        polyline.points[1].co = newPt
                        oldPt = newPt
            layerObject = bpy.data.objects.new(layerName, curveData)
            scn.objects.link(layerObject)
            scn.objects.active = layerObject


        # print('-------------- done -------------')


   
   
    ##### DISPATCH #####
    def dispatch(self, tokens):
        if tokens[0] in dir(self):
            eval('self.' + tokens[0] + '(' + str(tokens[1:]) + ')')
        else:
            print( 'unknown command:' + str(tokens[0]))

    ##### newPoly #####
    def newPoly(self):
        # stash points into curves
        # need to make this a copy
        if len(self.points) > 0:
            #print( 'poly with %d points' % (len(self.points)) )
            #for i,p in enumerate(self.points):
            #    print( '\t %d %s' % (i, str(p)) )
            self.polys.append( self.points[:] )
            self.points = []
    
    ##### newLayer #####
    def newLayer(self, delta):
        # stash existing points into curve
        self.newPoly()

        # stash existing set of polys into layer
        if len(self.polys) > 0:
            #print( 'new layer with %d polys' % len(self.polys) )
            self.layers.append( self.polys[:] )
            
            self.polys = []

            if delta > 0.0 and delta < 1.0:
                if delta in self.thickness.keys():
                    self.thickness[delta] = self.thickness[delta] + 1
                else:
                    self.thickness[delta] = 1
    
    ##### moveTo #####
    def moveTo(self, newPos):
        if newPos['Z'] != self.pos['Z']:
            delta = newPos['Z'] - self.pos['Z']
            self.newLayer(delta)
        
        if newPos['E'] <= self.pos['E'] or newPos['E'] <= 0.0:
            self.newPoly()
        
        if newPos['E'] > 0 and newPos['E'] >= self.pos['E']:
            self.points.append([newPos['X'],
                            newPos['Y'],
                            newPos['Z']])
        
        # should this be an explicit copy?
        self.pos = copy.deepcopy(newPos)


    ###### parseCoords ######
    def parseCoords(self, tokens):
        npos = { }
        for tok in tokens:
            axis = tok[0]
            if axis in ['X', 'Y', 'Z', 'E']:
                npos[axis] = float(tok[1:])
        return npos
    
    ##### parseCoordsUpdate #####
    def parseCoordsUpdate(self, tokens):
        npos = self.parseCoords(tokens)
        
        for axis in ['X', 'Y', 'Z', 'E']:
            if axis not in npos.keys():
                npos[axis] = self.pos[axis]
                
        #print('coord: %8g %8g %8g  %g' % (npos['X'], npos['Y'], npos['Z'], npos['E']))
        return npos
                

    def N(self, tokens):
        '''line number and checksum'''
        # checksum not implemented
        self.dispatch(tokens[1:])

    def G0(self, tokens):
        '''move fast'''

        newPos = self.parseCoordsUpdate(tokens)
        self.moveTo(newPos)
        

    def G1(self, tokens):
        '''move to'''
        self.G0(tokens)

    def G21(self,tokens):
        '''set units mm'''
        pass

    def G28(self, tokens):
        '''move to origin'''
        
        npos = self.pos
        for tok in tokens:
           axis = tok[0]
           if axis in ['X', 'Y', 'Z', 'E']:
               # note that value is ignored
               npos[axis] = 0.0

        # no matter what we won't be extruding
        npos['E'] = 0.0
        self.moveTo(npos)

    def G90(self, tokens):
        '''set absolute positioning'''
        pass

    def G92(self, tokens):
        '''set position'''
        # fortunately Slic3r does not set arbitrary coordinates
        # or do relative positioning.  This is used just to zero
        # out the position on the extruder.

        newPos = self.parseCoordsUpdate(tokens)
        if newPos['E'] == 0:
            self.newPoly()

        self.pos = newPos

    def M82(self, tokens):
        '''set extruder absolute mode'''
        pass

    def M84(self, tokens):
        '''stop idle hold'''
        pass

    def M104(self,tokens):
        '''set extruder temperature'''
        pass

    def M106(self, tokens):
        '''fan on'''
        pass

    def M107(self,tokens):
        '''fan off'''
        pass

    def M109(self,tokens):
        '''set extruder temperature and wait'''
        pass




def menu_func(self, context):
    self.layout.operator(IMPORT_OT_gcode.bl_idname, text="Slic3r GCode (.gcode)", icon='PLUGIN')

def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(menu_func)

def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(menu_func)

if __name__ == "__main__":
    register()

