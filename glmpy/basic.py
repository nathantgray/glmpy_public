import warnings
from glmpy import glmanip
import shutil
import subprocess
from pathlib import Path
import pandas as pd
import os


class Gridlabd:
    def __init__(self, file_path=None, base_dir_path=None):
        """

        Parameters
        ----------
        file_path
        base_dir_path
        """

        self.model = {}
        self.clock = {}
        self.directives = {}
        self.modules = {}
        self.classes = {}
        self.schedules = {}
        self.file_path = file_path
        self.base_dir_path = base_dir_path
        if file_path is not None:
            self.file_path = Path(file_path)
            if self.base_dir_path is None:
                self.base_dir_path = self.file_path.parent
            self.base_dir_path = Path(self.base_dir_path)
            self.read(self.file_path, self.base_dir_path)

    def read(self, file_path, base_dir):
        """

        Parameters
        ----------
        file_path: str or Path -- path of glm file
        base_dir: str or Path -- path of model base directory,

        Returns
        -------

        """
        self.model, self.clock, self.directives, self.modules, self.classes, self.schedules = \
            glmanip.parse(glmanip.read(file_path, base_dir))

    def write(self, filename):
        glmanip.write(filename, self.model, self.clock, self.directives, self.modules, self.classes, self.schedules)

    def find_objects_with_property_value(self, obj_property: str, value: str, search_types: list = None, prepend_class=False):
        """

        Parameters
        ----------
        obj_property: str
        value: str -- value of property
        search_types: list -- optional list of types to search for the object in
        prepend_class: bool -- if true, returned object names will be prepended with the object type e.g. node:node_1

        Returns
        -------
        list of object names which have the property with the given value

        """
        if search_types is None:
            search_types = self.model.keys()
        obj_list = []
        for obj_type in search_types:
            if obj_type in self.model.keys():
                for obj_name in self.model.get(obj_type):
                    if self.model[obj_type][obj_name].get(obj_property) == value:
                        if prepend_class:
                            obj_list.append(obj_type.strip("\'").strip("\"") + ':' + obj_name.strip("\'").strip("\""))
                        else:
                            obj_list.append(obj_name)
        return obj_list

    def get_object_type(self, obj_name: str, search_types: list = None):
        """

        Parameters
        ----------
        obj_name: str -- object name
        search_types: list -- optional list of types to search for the object in

        Returns
        -------
        name of the class that the object belongs to
        """
        if len(obj_name.split(":")) == 2:  # support receiving obj_name in the form class:obj_name e.g. "meter:node_2"
            class_name = obj_name.split(":")[0]
            return class_name
        if search_types is None:
            search_types = self.model.keys()
        for class_name in search_types:
            if class_name in self.model.keys():
                if obj_name in self.model[class_name].keys():
                    return class_name
        raise Warning("Did not find object class")

    def get_object_property_value(self, obj_name: str, obj_property: str, search_types: list = None):
        """

        Parameters
        ----------
        obj_name: str -- object name
        obj_property: str -- property to get the value of
        search_types: list -- optional list of types to search for the object in

        Returns
        -------
        value of property of the object
        """
        if len(obj_name.split(":")) == 2:  # support receiving obj_name in the form class:obj_name e.g. "meter:node_2"
            obj_class = obj_name.split(":")[0]
            obj_name = obj_name.split(":")[-1]
        else:
            obj_class = self.get_object_type(obj_name, search_types=search_types)
        if self.model[obj_class].get(obj_name) is None:
            return self.model[obj_class].get('\"' + obj_name + '\"').get(obj_property)
        return self.model[obj_class][obj_name].get(obj_property)

    def get_parent(self, obj_name: str, obj_type: str):
        """
        get parent of object
        Parameters
        ----------
        obj_name: str -- name of object
        obj_type: str -- type of object

        Returns
        -------
        parent_name: str
        parent_type: str
        """
        # 1. get name of parent
        parent_name = self.model[obj_type][obj_name].get('parent')
        # 2. get type of parent
        parent_type = None
        if parent_name is not None:
            parent_type = self.get_object_type(parent_name)
        return parent_name, parent_type

    def get_final_parent(self, obj_name: str, obj_type: str):
        """
        get ultimate parent of object
        Parameters
        ----------
        obj_name: str -- name of object
        obj_type: str -- type of object

        Returns
        -------
        parent_name: str
        parent_type: str
        """
        parent_name, parent_type = self.get_parent(obj_name, obj_type)
        if parent_type is not None:
            if self.model[parent_type][parent_name].get('parent') is None:
                return parent_name, parent_type
            else:
                return self.get_final_parent(parent_name, parent_type)

    def run(self, tmp_model_path=None, file_names_to_read=None):
        """
        Run the model in a temporary directory and read the result files into data frames.
        Parameters
        ----------
        tmp_model_path: str or Path -- directory where temporary directory will be created to store model and outputs
        file_names_to_read: list -- list of names of output files to read

        Returns
        -------
        dictionary of results as pandas dataframes
        """

        if self.base_dir_path is None:
            raise RuntimeError("Please define parameter, base_dir_path, before running.")
        # 1. Create temporary directory for storing and running the model
        if tmp_model_path is None:
            tmp_model_path = self.base_dir_path
        tmp_dir = Path(tmp_model_path) / 'gld_tmp'
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)  # remove old temporary directory
        tmp_dir.mkdir()
        output_name = tmp_dir / 'system.glm'
        # 2. Check for players and copy player files
        if self.model.get('player') is not None:
            player_dir = tmp_dir / 'players'
            player_dir.mkdir()
            for player_name in self.model['player'].keys():
                if self.model['player'][player_name].get('file') is not None:
                    old_path_name = (self.base_dir_path/Path(self.model['player'][player_name].get('file'))).absolute()
                    shutil.copy(old_path_name, player_dir/old_path_name.name)
                    self.model['player'][player_name]['file'] = str(Path('players/'+old_path_name.name))
                    #/home/nathangray/PycharmProjects/glmpy_public/glmpy/unittest/case/players/load_3_pA.player
        # 3. Create sub-directory for output files to go to.
        out_dir = tmp_dir / 'output'
        out_dir.mkdir()
        self.change_output_dirs('output')

        # 4. Write glm file
        self.write(output_name)
        # 5. Run glm file
        # self.run_gld_on_subprocess(output_name.name, tmp_dir)
        subprocess.run(["gridlabd", output_name.name], env=os.environ, cwd=tmp_dir)
        # 6. Read results
        results = {}
        if file_names_to_read is None:
            for file in list(out_dir.glob('*.csv')):
                results[Path(file).name] = self.read_csv(file)
        else:
            for file in file_names_to_read:
                file = Path('output')/file
                results[Path(file).name] = self.read_csv(file)
        return results

    # ~~~~~~~~~~ Methods for manipulating the model ~~~~~~~~~~~~~
    def remove_quotes_from_obj_names(self):
        """
        Use this to remove all quotes from object names and references. They aren't necessary.
        You may want to use this if quotes cause problems for processing.
        """
        model = {}
        for obj_class, class_dict in self.model.items():
            model[obj_class] = {}
            for obj_name, obj_dict in class_dict.items():
                model[obj_class][obj_name.strip('\"').strip('\'')] = obj_dict
        self.model = model
        link_types = [
            'link', 'overhead_line', 'underground_line', 'triplex_line', 'transformer',
            'regulator', 'fuse', 'switch', 'recloser', 'relay', 'sectionalizer', 'series_reactor'
        ]

        # Remove Quotes from references as well
        for link_type in link_types:
            if self.model.get(link_type) is not None:
                for link_name in self.model[link_type].keys():
                    if self.model[link_type][link_name].get('from') is not None:
                        self.model[link_type][link_name]['from'] = \
                            self.model[link_type][link_name]['from'].strip('\"').strip('\'')
                    if self.model[link_type][link_name].get('to') is not None:
                        self.model[link_type][link_name]['to'] = \
                            self.model[link_type][link_name]['to'].strip('\"').strip('\'')
                    # clean configuration references
                    if link_type in ['overhead_line', 'underground_line', 'transformer', 'regulator'] :
                        if self.model[link_type][link_name].get('configuration') is not None:
                            self.model[link_type][link_name]['configuration'] = \
                                self.model[link_type][link_name]['configuration'].strip('\"').strip('\'')

        node_types = ['meter', 'node', 'triplex_node', 'triplex_meter', 'load', 'pqload', 'capacitor', 'recorder']
        for obj_type in node_types:
            if self.model.get(obj_type) is not None:
                for obj_name in self.model[obj_type].keys():
                    if self.model[obj_type][obj_name].get('parent') is not None:
                        self.model[obj_type][obj_name]['parent'] = \
                            self.model[obj_type][obj_name]['parent'].strip('\"').strip('\'')
        # remove quotes from all line_configuration properties since they are all links to other objects.
        if self.model.get('line_configuration') is not None:
            for obj_name in self.model['line_configuration'].keys():
                for obj_property in self.model['line_configuration'][obj_name].keys():
                    self.model['line_configuration'][obj_name][obj_property] = \
                        self.model['line_configuration'][obj_name][obj_property].strip('\"').strip('\'')

    def change_output_dirs(self, new_output_dir):
        """
        Modify all of the output file paths to have the path provided.

        Parameters
        ----------
        new_output_dir: str or Path -- directory to send all output files to.
        """
        # filename in voltdump, currdump, impedance_dump
        # file in recorder, collector, group_recorder
        for o_type in ['voltdump', 'currdump', 'impedance_dump']:
            if self.model.get(o_type) is not None:
                for o_name in self.model[o_type].keys():
                    if self.model[o_type][o_name].get('filename') is not None:
                        original_path = Path(self.model[o_type][o_name].get('filename'))
                        new_path = Path(new_output_dir) / original_path.name
                        self.model[o_type][o_name]['filename'] = new_path
        for o_type in ['recorder', 'collector', 'group_recorder', 'multi_recorder']:
            if self.model.get(o_type) is not None:
                for o_name in self.model[o_type].keys():
                    if self.model[o_type][o_name].get('file') is not None:
                        original_path = Path(self.model[o_type][o_name].get('file'))
                        new_path = Path(new_output_dir) / original_path.name
                        self.model[o_type][o_name]['file'] = new_path

    def change_player_dirs(self, new_player_dir):
        o_type = 'player'
        if self.model.get(o_type) is not None:
            for o_name in self.model[o_type].keys():
                if self.model[o_type][o_name].get('file') is not None:
                    original_path = Path(self.model[o_type][o_name].get('file'))
                    new_path = Path(new_player_dir) / original_path.name
                    self.model[o_type][o_name]['file'] = new_path

    def add_object(self, obj_type, obj_name, **params):
        """
        A convenience function for adding an object to the model. This will overwrite existing objects.

        Parameters
        ----------
        obj_type: str -- type of object
        obj_name: str -- name of object
        params: Keyword arguments become parameters of the object.
                Some property names are not allowed as keywords in Python.
                To get around this problem, pass the parameters as a dictionary with ** in front:
                add_object(obj_type, obj_name, **{'from': 'bus_3', 'to': 'bus_4', ...}).
        """
        if self.model.get(obj_type) is None:
            self.model[obj_type] = {}
        if self.model[obj_type].get(obj_name) is not None:
            warnings.warn(f'Overwriting object, {obj_name}!')
        self.model[obj_type][obj_name] = params

    def add_module(self, module_name, **params):
        """
        A convenience function for adding a module. If the module already exists it will overwrite existing parameters.
        Parameters
        ----------
        module_name: str -- name of module to add
        params: Keyword arguments become parameters of the module.
                Some property names are not allowed as keywords in Python.
                To get around this problem, pass the parameters as a dictionary with ** in front:
                add_module(obj_type, obj_name, **{property1: prop_val1, ...}).
        """
        if self.modules.get(module_name) is None:
            self.modules[module_name] = params
        else:
            warnings.warn(f'Overwriting module, {module_name}, parameters!')
            self.modules[module_name] = params

    def require_module(self, module_name, **params):
        """
        Will ensure that the module is included. If not it will be added. If it is included it will do nothing.
        This is similar to add_module but does not overwrite parameters if it already exists
        Parameters
        ----------
        module_name
        params

        """
        if self.modules.get(module_name) is None:
            self.modules[module_name] = params

    def add_helics(self, federate_name, config_path):
        """
        Add everything the model needs to enable HELICS use with GridLAB-D
        Parameters
        ----------
        federate_name: str -- name of federate
        config_path: str or Path -- path to HELICS configuration file

        Returns
        -------

        """
        self.require_module('connection')
        self.add_object('helics_msg', federate_name, configure=Path(config_path).as_posix())

    def remove_helics(self):
        """
        Remove HELICS from model so it can run independently.
        """
        if self.model.get('helics_msg') is not None:
            del self.model['helics_msg']

    # ~~~~~~~~~~ Static Methods ~~~~~~~~~~~~~
    @staticmethod
    def read_csv(filepath):
        """
        Read GridLAB-D output csv file into a dataframe. This will automatically choose the appropriate header line.
        Parameters
        ----------
        filepath

        """
        try:
            df = pd.read_csv(
                filepath,
                sep=',',
                header=1, index_col=0)
        except pd.errors.ParserError:
            df = pd.read_csv(
                filepath,
                sep=',',
                header=8, index_col=0)
        return df