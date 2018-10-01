#!/usr/bin/env python

import numpy as np
import yaml

from PyCT.core import Material, Neighbors, System, Run


def material_preprod(dst_path):
    # Load simulation parameters
    sim_param_file_name = 'simulation_parameters.yml'
    sim_param_file_path = dst_path / sim_param_file_name
    with open(sim_param_file_path, 'r') as stream:
        try:
            sim_params = yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    # data type conversion:
    sim_params['system_size'] = np.asarray(sim_params['system_size'])
    sim_params['pbc'] = np.asarray(sim_params['pbc'])
    sim_params['species_count'] = np.asarray(sim_params[
                                                    'species_count'])

    # Load material parameters
    config_file_name = 'sys_config.yml'
    if sim_params['work_dir_depth'] == 0:
        input_directory_path = (
                dst_path.resolve() / sim_params['input_file_directory_name'])
    else:
        input_directory_path = (
            dst_path.resolve().parents[sim_params['work_dir_depth'] - 1]
            / sim_params['input_file_directory_name'])
    config_file_path = input_directory_path / config_file_name
    with open(config_file_path, 'r') as stream:
        try:
            params = yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    input_coordinate_file_name = 'POSCAR'
    input_coord_file_location = input_directory_path.joinpath(
                                            input_coordinate_file_name)
    params.update({'input_coord_file_location':
                   input_coord_file_location})
    config_params = ReturnValues(params)

    # Build material object files
    material_info = Material(config_params)

    # Build neighbors object files
    material_neighbors = Neighbors(material_info,
                                   sim_params['system_size'],
                                   sim_params['pbc'])

    file_exists = 0
    if dst_path.joinpath('Run.log').exists():
        file_exists = 1
    if not file_exists or sim_params['over_write']:
        # Load input files to instantiate system class
        hop_neighbor_list_file_name = input_directory_path.joinpath(
                                            'hop_neighbor_list.npy')
        hop_neighbor_list = np.load(hop_neighbor_list_file_name)[()]
        cumulative_displacement_list_file_path = (
                            input_directory_path.joinpath(
                                'cumulative_displacement_list.npy'))
        cumulative_displacement_list = np.load(
                                cumulative_displacement_list_file_path)
        alpha = config_params.alpha
        n_max = config_params.n_max
        k_max = config_params.k_max
        
        # Load step hop neighbor list if needed
        step_system_size_array = []
        step_hop_neighbor_master_list = []
        if 'doping' in sim_params:
            for map_index, insertion_type in enumerate(sim_params['doping']['insertion_type']):
                if insertion_type == 'gradient':
                    gradient_params = sim_params['doping']['gradient'][map_index]
                    ld = gradient_params['ld']
                    step_length_ratio = gradient_params['step_length_ratio']
                    sum_step_length_ratio = sum(step_length_ratio)
                    stepwise_num_dopants = gradient_params['stepwise_num_dopants']
                    if any(stepwise_num_dopants):
                        num_steps = len(step_length_ratio)
                    else:
                        num_steps = 0
                    for step_index in range(num_steps):
                        import_flag = 0
                        step_system_size = np.copy(sim_params['system_size'])
                        step_system_size[ld] *= step_length_ratio[step_index] / sum_step_length_ratio
                        if len(step_system_size_array) == 0:
                            step_system_size_array = step_system_size
                            import_flag = 1
                        elif len(step_system_size_array.shape) == 1:
                            if not np.array_equal(step_system_size_array,
                                                  step_system_size):
                                step_system_size_array = np.vstack((step_system_size_array,
                                                                    step_system_size))
                                import_flag = 1
                        else:
                            lookup_array = np.where((step_system_size_array == step_system_size).all(axis=1))[0]
                            if len(lookup_array) == 0:
                                step_system_size_array = np.vstack((step_system_size_array,
                                                                    step_system_size))
                                import_flag = 1
                        if import_flag:
                            step_input_directory_path = (
                                dst_path.resolve().parents[sim_params['doping']['step_work_dir_depth'] - 1]
                                / ('SystemSize[' + ','.join(str(element) for element in step_system_size) + ']')
                                / sim_params['input_file_directory_name'])
                            step_hop_neighbor_list_file_name = step_input_directory_path.joinpath(
                                                                        'hop_neighbor_list.npy')
                            step_hop_neighbor_list = np.load(step_hop_neighbor_list_file_name)[()]
                            step_hop_neighbor_master_list.append(step_hop_neighbor_list)

        material_system = System(
            material_info, material_neighbors, hop_neighbor_list,
            cumulative_displacement_list, alpha, n_max, k_max,
            step_system_size_array, step_hop_neighbor_master_list)

        # Load precomputed array to instantiate run class
        precomputed_array_file_path = input_directory_path.joinpath(
                                            'precomputed_array.npy')
        precomputed_array = np.load(precomputed_array_file_path)
        material_run = Run(
            material_system, precomputed_array, sim_params['temp'],
            sim_params['ion_charge_type'],
            sim_params['species_charge_type'], sim_params['n_traj'],
            sim_params['t_final'], sim_params['time_interval'],
            sim_params['species_count'], sim_params['initial_occupancy'],
            sim_params['relative_energies'], sim_params['external_field'],
            sim_params['doping'])
        material_run.preproduction(dst_path, sim_params['random_seed'])
    else:
        print('Simulation files already exists in '
              + 'the destination directory')
    return None


class ReturnValues(object):
    """dummy class to return objects from methods \
        defined inside other classes"""
    def __init__(self, input_dict):
        for key, value in input_dict.items():
            setattr(self, key, value)
