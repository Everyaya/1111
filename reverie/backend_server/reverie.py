import json
import numpy
import datetime
import pickle
import time
import math
import os
import shutil
import traceback

from selenium import webdriver

from global_methods import *
from utils import *
from maze import *
from persona.persona import *


class ReverieServer:
    def __init__(self, fork_sim_code, sim_code):
        # FORKING FROM A PRIOR SIMULATION:
        # <fork_sim_code> indicates the simulation we are forking from.
        # Interestingly, all simulations must be forked from some initial
        # simulation, where the first simulation is "hand-crafted".
        self.fork_sim_code = fork_sim_code
        fork_folder = os.path.join(fs_storage, self.fork_sim_code)

        # <sim_code> indicates our current simulation. The first step here is to
        # copy everything that's in <fork_sim_code>, but edit its
        # reverie/meta/json's fork variable.
        self.sim_code = sim_code
        sim_folder = os.path.join(fs_storage, self.sim_code)

        # 调试路径
        print(f"Fork folder path: {fork_folder}")
        print(f"Simulation folder path: {sim_folder}")

        # 检查源文件夹是否存在
        if not os.path.exists(fork_folder):
            raise FileNotFoundError(f"Source folder does not exist: {fork_folder}")

        copyanything(fork_folder, sim_folder)

        with open(os.path.join(sim_folder, "reverie", "meta.json")) as json_file:
            reverie_meta = json.load(json_file)

        with open(os.path.join(sim_folder, "reverie", "meta.json"), "w") as outfile:
            reverie_meta["fork_sim_code"] = fork_sim_code
            outfile.write(json.dumps(reverie_meta, indent=2))

        # LOADING REVERIE'S GLOBAL VARIABLES
        self.start_time = datetime.datetime.strptime(f"{reverie_meta['start_date']}, 00:00:00", "%B %d, %Y, %H:%M:%S")
        self.curr_time = datetime.datetime.strptime(reverie_meta['curr_time'], "%B %d, %Y, %H:%M:%S")
        self.sec_per_step = reverie_meta['sec_per_step']
        self.maze = Maze(reverie_meta['maze_name'])
        self.step = reverie_meta['step']

        # SETTING UP PERSONAS IN REVERIE
        self.personas = dict()
        self.personas_tile = dict()

        # Loading in all personas.
        init_env_file = os.path.join(sim_folder, "environment", f"{str(self.step)}.json")
        init_env = json.load(open(init_env_file))
        for persona_name in reverie_meta['persona_names']:
            persona_folder = os.path.join(sim_folder, "personas", persona_name)
            p_x = init_env[persona_name]["x"]
            p_y = init_env[persona_name]["y"]
            curr_persona = Persona(persona_name, persona_folder)

            self.personas[persona_name] = curr_persona
            self.personas_tile[persona_name] = (p_x, p_y)
            self.maze.tiles[p_y][p_x]["events"].add(curr_persona.scratch.get_curr_event_and_desc())

        # REVERIE SETTINGS PARAMETERS:
        self.server_sleep = 0.1

        # SIGNALING THE FRONTEND SERVER:
        curr_sim_code = {"sim_code": self.sim_code}
        with open(os.path.join(fs_temp_storage, "curr_sim_code.json"), "w") as outfile:
            outfile.write(json.dumps(curr_sim_code, indent=2))

        curr_step = {"step": self.step}
        with open(os.path.join(fs_temp_storage, "curr_step.json"), "w") as outfile:
            outfile.write(json.dumps(curr_step, indent=2))

    def save(self):
        sim_folder = os.path.join(fs_storage, self.sim_code)
        reverie_meta = {
            "fork_sim_code": self.fork_sim_code,
            "start_date": self.start_time.strftime("%B %d, %Y"),
            "curr_time": self.curr_time.strftime("%B %d, %Y, %H:%M:%S"),
            "sec_per_step": self.sec_per_step,
            "maze_name": self.maze.maze_name,
            "persona_names": list(self.personas.keys()),
            "step": self.step
        }
        reverie_meta_f = os.path.join(sim_folder, "reverie", "meta.json")
        with open(reverie_meta_f, "w") as outfile:
            outfile.write(json.dumps(reverie_meta, indent=2))

        for persona_name, persona in self.personas.items():
            save_folder = os.path.join(sim_folder, "personas", persona_name, "bootstrap_memory")
            persona.save(save_folder)

    def start_server(self, int_counter):
        sim_folder = os.path.join(fs_storage, self.sim_code)
        game_obj_cleanup = dict()

        while True:
            if int_counter == 0:
                break

            curr_env_file = os.path.join(sim_folder, "environment", f"{self.step}.json")
            if check_if_file_exists(curr_env_file):
                try:
                    with open(curr_env_file) as json_file:
                        new_env = json.load(json_file)
                        env_retrieved = True
                except:
                    env_retrieved = False

                if env_retrieved:
                    for key, val in game_obj_cleanup.items():
                        self.maze.turn_event_from_tile_idle(key, val)
                    game_obj_cleanup = dict()

                    for persona_name, persona in self.personas.items():
                        curr_tile = self.personas_tile[persona_name]
                        new_tile = (new_env[persona_name]["x"], new_env[persona_name]["y"])

                        self.personas_tile[persona_name] = new_tile
                        self.maze.remove_subject_events_from_tile(persona.name, curr_tile)
                        self.maze.add_event_from_tile(persona.scratch.get_curr_event_and_desc(), new_tile)

                        if not persona.scratch.planned_path:
                            game_obj_cleanup[persona.scratch.get_curr_obj_event_and_desc()] = new_tile
                            self.maze.add_event_from_tile(persona.scratch.get_curr_obj_event_and_desc(), new_tile)
                            blank = (persona.scratch.get_curr_obj_event_and_desc()[0], None, None, None)
                            self.maze.remove_event_from_tile(blank, new_tile)

                    movements = {"persona": dict(), "meta": dict()}
                    for persona_name, persona in self.personas.items():
                        next_tile, pronunciatio, description = persona.move(
                            self.maze, self.personas, self.personas_tile[persona_name], self.curr_time)
                        movements["persona"][persona_name] = {
                            "movement": next_tile,
                            "pronunciatio": pronunciatio,
                            "description": description,
                            "chat": persona.scratch.chat
                        }

                    movements["meta"]["curr_time"] = self.curr_time.strftime("%B %d, %Y, %H:%M:%S")

                    curr_move_dir = os.path.join(sim_folder, "movement")
                    if not os.path.isdir(curr_move_dir):
                        os.mkdir(curr_move_dir)
                    curr_move_file = os.path.join(curr_move_dir, f"{self.step}.json")
                    with open(curr_move_file, "w") as outfile:
                        outfile.write(json.dumps(movements, indent=2))

                    self.step += 1
                    self.curr_time += datetime.timedelta(seconds=self.sec_per_step)

                    int_counter -= 1

            time.sleep(self.server_sleep)

    def open_server(self):
        print(
            "Note: The agents in this simulation package are computational constructs powered by generative agents architecture and LLM. We clarify that these agents lack human-like agency, consciousness, and independent decision-making.\n---")

        sim_folder = os.path.join(fs_storage, self.sim_code)

        while True:
            sim_command = input("Enter option: ").strip()
            ret_str = ""

            try:
                if sim_command.lower() in ["f", "fin", "finish", "save and finish"]:
                    self.save()
                    break

                elif sim_command.lower() == "start path tester mode":
                    shutil.rmtree(sim_folder)
                    self.start_path_tester_server()

                elif sim_command.lower() == "exit":
                    shutil.rmtree(sim_folder)
                    break

                elif sim_command.lower() == "save":
                    self.save()

                elif sim_command[:3].lower() == "run":
                    int_count = int(sim_command.split()[-1])
                    self.start_server(int_count)

                # 其他命令处理...

                print(ret_str)

            except:
                traceback.print_exc()
                print("Error.")
                pass


if __name__ == '__main__':
    origin = input("Enter the name of the forked simulation: ").strip()
    target = input("Enter the name of the new simulation: ").strip()

    rs = ReverieServer(origin, target)
    rs.open_server()
