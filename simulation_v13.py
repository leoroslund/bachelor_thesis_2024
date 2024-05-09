import numpy as np 
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import simpy
from dataclasses import dataclass, field
from cycler import cycler

class worksite():
    def __init__(self, env, *, num_chargers: int = None, charging_power: int = 150, charging_threshold: float = 0.1,
                 num_wl: int = None, num_ex_b: int = None, num_ex_c: int = None, num_du: int = None,
                 workday: int = 9*3600, break_1: int = 2*3600, break_2: int = 5*3600, break_duration: int = 30*60,
                 wl_config: dict = {}, ex_config: dict = {}, du_config: dict = {}) -> None:
        
        self.env: simpy.Environment = env
        self.chargers = simpy.Resource(env, capacity=num_chargers)
        self.charging_power: float = charging_power/3600 #kW/s
        self.charging_threshold: float = charging_threshold #%
        self.data: dict = {"battery_levels":[],
                           "power":{},
                           "inactive_machines":{}}

        # Workday
        self.workday: int = workday
        self.break_1: int = break_1
        self.break_2: int = break_2
        self.break_duration: int = break_duration

        # Machines
        self.wl_machines = [Machine(env=env, id=f"HL #{i+1}", **wl_config) for i in range(num_wl)]
        self.du_machines = [Machine(env=env, id=f"DU #{i+1}", **du_config) for i in range(num_du)]
        self.ex_machines_b = [Machine(env=env, id=f"BG #{i+1}", **ex_config) for i in range(num_ex_b)]
        self.ex_machines_c = [Machine(env=env, id=f"BGK #{i+1}", **ex_config) for i in range(num_ex_c)]

        for machine in self.ex_machines_b:
            env.process(self.operate_break(machine))

        for machine in self.ex_machines_c:
            env.process(self.operate_cable(machine))

        for machine in self.du_machines:
            env.process(self.operate_break(machine))

        for machine in self.wl_machines:
            env.process(self.operate_break(machine))
            
    def operate_cable(self, machine):
        # Two breaks
        break_1: int = self.break_1
        break_2: int = self.break_2
        break_time: int = self.break_duration

        # Machine configurations
        high_power: int = machine.high_power
        high_time: int = machine.high_time
        low_power: int = machine.low_power
        low_time: int = machine.low_time

        while True:
            # Having breaks at set times, 30 min each
            if self.env.now == break_1 or self.env.now == break_2:
                yield self.env.timeout(break_time)

            # Operating pattern with logging    
            else:
                for _ in range(low_time):
                    yield self.env.timeout(1)
                    self.log_power(low_power)
                    
                for _ in range(high_time):
                    yield self.env.timeout(1)
                    self.log_power(high_power)

    def operate_break(self, machine):
        operating_power: float = machine.operating_power
        charging_threshold: float = self.charging_threshold
        charging_time: int = self.break_duration

        # Two breaks and a charging stop last half hour
        break_1: int = self.break_1
        break_2: int = self.break_2
        no_charging: int = self.workday-1800

        while True:
            self.log_battery_level(machine)
            self.log_machines()
            yield self.env.timeout(1)

            # If break time, charge
            if self.env.now == break_1  or self.env.now == break_2:
                yield self.env.process(self.charge(machine, charging_time))

            if machine.battery.level > charging_threshold*machine.battery.capacity:
                yield machine.battery.get(operating_power)
            else:
                if self.env.now < no_charging:
                    yield self.env.process(self.charge(machine, charging_time))
                else:
                    if machine.battery.level > operating_power:
                        yield machine.battery.get(operating_power)
                    else:
                        self.data["inactive_machines"][self.env.now-1] += 1
        
    def charge(self, machine: object, duration: int):
        charging_power: float = self.charging_power
        charging_power_kW: int = charging_power*3600
        
        # Start queueing
        with self.chargers.request() as request:
            # Continue to work while queueing
            while not request.triggered:
                self.log_battery_level(machine)
                self.log_machines()
                yield self.env.timeout(1)
                if machine.battery.level > machine.operating_power:
                    yield machine.battery.get(machine.operating_power)
                else:
                    self.data["inactive_machines"][self.env.now-1] += 1

            # When charger is available
            yield request
            # Charging battery and logging data
            for s in range(duration):
                self.log_battery_level(machine)
                self.log_machines()
                yield self.env.timeout(1)
                if machine.battery.level + charging_power < machine.battery.capacity:
                    yield machine.battery.put(charging_power)

                self.log_power(charging_power_kW)
    
    def log_battery_level(self, machine):
        self.data["battery_levels"].append((self.env.now, machine.id, machine.battery.level))
        
    def log_power(self, charging_power):
        time: int = self.env.now
        if time in self.data['power']:
            self.data['power'][time] += charging_power
        else:
            self.data['power'][time] = charging_power

    def log_machines(self):
        time: int = self.env.now
        self.data["inactive_machines"][time] = len(self.chargers.users)

@dataclass
class Machine:
    env: simpy.Environment
    id: str
    battery_capacity: int
    operating_power: float
    high_power: int = None
    low_power: int = None
    high_time: int = None
    low_time: int = None

    battery: simpy.Container = field(init=False)

    def __post_init__(self):
        self.battery = simpy.Container(self.env, init=self.battery_capacity, capacity=self.battery_capacity)

def main(setting: str, chargers: int = 2, excavator_bat: int = 0, charging_power=150):
    excavator_str: str = "K"
    if excavator_bat != 0:
        excavator_str = "B"

    def prepare_data(data) -> tuple[list, list, list]:
        # Retrieving the battery levels in format (time, id, battery level)
        battery_levels: tuple = data["battery_levels"]

        battery_levels_by_machine: dict[str, tuple] = {}
        for time, machine_id, level in battery_levels:
            if machine_id not in battery_levels_by_machine:
                battery_levels_by_machine[machine_id] = []
            battery_levels_by_machine[machine_id].append((time, level))

        grid_power_list: list[int] = []
        for t in time_array:
            grid_power_list.append(data['power'].get(t, 0) + base_load)

        active_machines: list[int] = []
        for t in time_array:
            if t > break_1 and t < break_1 + break_duration:
                active_machines.append(total_machines - num_excavators_cable - data["inactive_machines"][t])
            elif t > break_2 and t < break_2 + break_duration:
                active_machines.append(total_machines - num_excavators_cable - data["inactive_machines"][t])
            else:
                active_machines.append(total_machines - data["inactive_machines"][t])

        return battery_levels_by_machine, grid_power_list, active_machines

    def plot_data(battery_levels_by_machine: dict, grid_power_list: list, active_machines: list, large: bool = False) -> None:    
        plt.style.use('leostyle2.mplstyle')

        def adjust_prop_cycler():
            # Extract current prop cycle
            current_cycler = plt.rcParams['axes.prop_cycle']
            color_cycle = current_cycler.by_key()['color']
            linestyle_cycle = current_cycler.by_key()['linestyle']
            
            # Skip the first two items in each cycle
            skipped_color_cycle = color_cycle[2:] + color_cycle[:2]
            skipped_linestyle_cycle = linestyle_cycle[2:] + linestyle_cycle[:2]
            
            # Combine the skipped cycles
            combined_cycler = cycler('color', skipped_color_cycle) + cycler('linestyle', skipped_linestyle_cycle)
            plt.rc('axes', prop_cycle=combined_cycler)

        setting: str = "MED"
        if large == True:
            setting = "LAR"

        def plot_setup(title: str, xlabel: str, ylabel: str, x_ticks: np.ndarray, formatter) -> None:
            plt.title(title)
            plt.xlabel(xlabel)
            plt.ylabel(ylabel)
            plt.xticks(x_ticks, rotation = 45)
            plt.gca().xaxis.set_major_formatter(FuncFormatter(formatter))
            plt.ylim(bottom=0)
            plt.tight_layout()
            if charging_power != 150:
                plt.savefig(f"./figs/{setting}{num_chargers}{excavator_str}{charging_power}_{title[0:3]}.png")
            else:
                plt.savefig(f"./figs/{setting}{num_chargers}{excavator_str}_{title[0:3]}.png")

            plt.clf()

        # Plot battery levels
        if excavator_bat == 0:
            adjust_prop_cycler()

        for machine_id, levels in battery_levels_by_machine.items():
            times, battery_levels = zip(*levels)
            plt.plot(times, battery_levels, label=f"{machine_id}")
        
        plt.legend()
        plot_setup("Batterinivåer över tid", "Tid", "Batterinivå [kWh]", x_ticks, ticks_to_time)

        # Plot power usage
        plt.style.use('leostyle2.mplstyle')
        plt.plot(time_array, grid_power_list)
        plot_setup("Total effekt över tid", "Tid", "Effekt [kW]", x_ticks, ticks_to_time)

        # Plot active machines
        plt.plot(time_array, active_machines)
        plot_setup("Aktiva maskiner över tid", "Tid", "Antal maskiner", x_ticks, ticks_to_time)

    def ticks_to_time(x: int, pos) -> str:
        hours: int = int((x+start_time) // 3600)
        minutes: int = int(((x+start_time) % 3600) // 60)
        return f'{hours:02d}:{minutes:02d}'
    
    env = simpy.Environment()

    # Time settings
    workday: int = 9*3600 # 8 hour workday 1 hour break 
    break_1: int = 2*3600 # First break after 2 hours (9:00)
    break_2: int = 5*3600 # Second break after 5 hours (12:00)
    break_duration: int = 30*60 # 30 minutes in seconds
    start_time: int = 25200 # 07:00

    # Chargers and config
    num_chargers: int = chargers
    charging_power: int = charging_power
    charging_threshold: float = 0.1
    base_load: int = 18 # kW

    # Number of machines
    num_wheel_loaders: int = 2
    num_excavators_battery: int = excavator_bat
    num_excavators_cable: int = 2 - excavator_bat
    num_dumpers: int = 2
    total_machines: int = num_wheel_loaders + num_dumpers + num_excavators_battery + num_excavators_cable

    # Machine config
    if setting.lower() == "med":
        excavator_conf: dict = {'battery_capacity': 264, 'operating_power': 109 / 3600,
                            'high_power': 169, 'low_power': 19, 'high_time': 6, 'low_time': 4}
        wheel_loader_conf: dict = {'battery_capacity': 237, 'operating_power': 47 / 3600}
        dumper_conf: dict = {'battery_capacity': 314, 'operating_power': 48 / 3600}
        large = False

    elif setting.lower() == "lar":
        excavator_conf: dict = {'battery_capacity': 568, 'operating_power': 191 / 3600,
                            'high_power': 296, 'low_power': 33, 'high_time': 6, 'low_time': 4}
        wheel_loader_conf: dict = {'battery_capacity': 451, 'operating_power': 94 / 3600}
        dumper_conf: dict = {'battery_capacity': 490, 'operating_power': 82 / 3600}
        large = True
    else:
        raise Exception("Choose between setting \'lar\' or \'med\'")

    # Creating worksite
    worksite_instance: worksite = worksite(env, num_chargers=num_chargers, charging_power=charging_power, charging_threshold=charging_threshold,
                                           num_du=num_dumpers, num_ex_b=num_excavators_battery, num_ex_c=num_excavators_cable, num_wl=num_wheel_loaders, 
                                           workday=workday, break_1=break_1, break_2=break_2, break_duration=break_duration, 
                                           wl_config=wheel_loader_conf, ex_config=excavator_conf, du_config=dumper_conf)

    env.run(until=workday)

    time_array: np.ndarray = np.arange(0, workday, 1)
    x_ticks: np.ndarray = np.arange(0, workday+1, 3600)

    # Calculating productivity
    battery_levels, total_power, active_machines = prepare_data(worksite_instance.data)
    sum_machines = sum(active_machines)
    total_work_hours = total_machines*8
    total_worked_hours = sum_machines/3600
    missed_hours = total_work_hours - total_worked_hours
    
    # Calculatning mean effect 
    sum_power = sum(total_power)
    mean_power = sum_power/workday

    print(f"{setting}{num_chargers}{excavator_str}{charging_power}")
    print(f"Timmar utan arbete [h]: {missed_hours :.2f}\n" + f"Produktivitet: {1-(missed_hours/total_work_hours) :.2%}\n"
          + f"Andel av totala timmar: {missed_hours/total_work_hours : .2%}")
    print(f"Medeleffekt [kW]: {mean_power:.2f}")
    plot_data(battery_levels, total_power, active_machines, large = large)

if __name__ == "__main__":
    main(setting="med", chargers=3, excavator_bat=2, charging_power=150)
