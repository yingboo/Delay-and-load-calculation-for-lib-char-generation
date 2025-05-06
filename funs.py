import numpy as np
import matplotlib.pyplot as plt
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *
import PySpice.Logging.Logging as Logging
import pandas as pd
from lmfit import Parameters, minimize
import os
from PySpice.Spice.Xyce.Server import XyceServer
import multiprocessing
# 启用日志
logger = Logging.setup_logging()

def run_ac_sweep_cgg( model_path="pyspice/netlists/test_modelcard.nmos_xyce", fixed_frequency=10@u_kHz):
    
    circuit = Circuit("BSIM-CMG Nmos")
    

    circuit.include(model_path)
    

    circuit.SinusoidalVoltageSource('ac', 'gate', 1, ac_magnitude=0.1, amplitude=0.1, frequency=1@u_kHz)
    circuit.X('n', 'nFinFet',circuit.gnd, 'gate', circuit.gnd, circuit.gnd)
    circuit.V('dc', 1, circuit.gnd, 1 @ u_V)
    

    simulator = circuit.simulator(
        simulator='xyce-parallel',
        temperature=27,
        nominal_temperature=27,
        xyce_command=r"C:\Program Files\Xyce_7.9\bin\Xyce.exe"
    )


    # Vdc_values = np.round(np.linspace(-1.2, 1.2, 25), decimals=1)

    # Vdc_values = Vdc_values[(Vdc_values != -1.1) & (Vdc_values != 1.1)]
    Vdc_values = np.round(np.linspace(-1.4, 1.4, 57), decimals=2)
    # Vdc_values = np.insert(Vdc_values,30,7.63278329e-16)
    Cgg_values = []
    Vgate_values = []

    # 执行 DC Sweep
    for idx, Vdc_value in enumerate(Vdc_values):

        circuit.element('Vdc').dc_value=Vdc_value

        try:

            ac_analysis = simulator.ac(
                start_frequency=fixed_frequency,
                stop_frequency=fixed_frequency,
                number_of_points=1,
                variation='dec'
            )

            gate_voltage = np.array(ac_analysis.gate)
            gate_current = np.array(ac_analysis['Vac'])
            

            factor = gate_voltage / gate_current
            # Cgg = 1e15 / (2 * np.pi * fixed_frequency * factor.imag)  # 计算电容值, unit=fF
            Cgg = 1 / (2 * np.pi * fixed_frequency * factor.imag)  # 计算电容值, unit=F
            

            Vg = Vdc_value
            

            Cgg_values.append(Cgg) 
            Vgate_values.append(Vg) 
            
            # print(f"Vdc = {Vdc_value} V: Cgg = {Cgg}, Vgate = {Vg}")
        
        except Exception as e:
            print(f"Error at Vdc = {Vdc_value} V: {e}")

    Cgg_values=np.array(Cgg_values)
    return Vgate_values, Cgg_values




def run_dc_sweep_vd_id(xyce_command=r"C:\Program Files\Xyce_7.9\bin\Xyce.exe"):
    

    circuit = Circuit("BSIM-CMG Nmos")


    circuit.include("netlists/test_modelcard.nmos_xyce")


    circuit.V('d', 'drain', circuit.gnd, 0)
    circuit.V('g', 'gate', circuit.gnd, 0)
    

    circuit.X('n', 'nFinFet','drain', 'gate', circuit.gnd, circuit.gnd)
    # circuit.MOSFET('n', 'drain', 'gate', circuit.gnd, circuit.gnd, model='nmos1')


    simulator = circuit.simulator(
        simulator='xyce-parallel',
        temperature=27,
        nominal_temperature=27,
        xyce_command=xyce_command
    )


    Vg_values = [1.2,1.0,0.75,0.375,0.05]  # Vg sweep
    Vd_values = np.linspace(0, 1.2, 25)  # Vd sweep

    Id_list = []  # 存储每个 Vg 下的 Id

    for Vg_value in Vg_values:

        if hasattr(circuit, 'Vg'):
            Vg = circuit.Vg.detach()
        circuit.V('g', 'gate', circuit.gnd, Vg_value @ u_V)


        try:
            dc_analysis = simulator.dc(Vd=slice(0, 1.2, 0.05))  # Vds sweep
            # print(f"DC analysis completed successfully for Vg = {Vg_value} V.")
            
            Id = -dc_analysis['Vd']
            
            Id_list.append(Id*1e6) #unit = uA
        
        except Exception as e:
            print(f"Error at Vg = {Vg_value} V: {e}")

    Id_values = np.array(Id_list)

    return Vd_values, Id_values


def run_dc_sweep_id_vs_vg(xyce_command=r"C:\Program Files\Xyce_7.9\bin\Xyce.exe"):
    

    circuit = Circuit("BSIM-CMG Nmos")


    circuit.include("netlists/test_modelcard.nmos_xyce")


    circuit.V('d', 'drain', circuit.gnd, 0)
    circuit.V('g', 'gate', circuit.gnd, 0)
    

    circuit.X('n', 'nFinFet','drain', 'gate', circuit.gnd, circuit.gnd)
    # circuit.MOSFET('n', 'drain', 'gate', circuit.gnd, circuit.gnd, model='nmos1')

  
    simulator = circuit.simulator(
        simulator='xyce-parallel',
        temperature=27,
        nominal_temperature=27,
        xyce_command=xyce_command
    )

    
    Vd_values = [1.2,1.0,0.75,0.375,0.05]  # Vd sweep
    Vg_values = np.linspace(0, 1.2, 25)  # Vg sweep

    Id_list = []  
    Id_lg_values= []

   
    for Vd_value in Vd_values:
        
        if hasattr(circuit, 'Vd'):
            Vd = circuit.Vd.detach()
        circuit.V('d', 'drain', circuit.gnd, Vd_value @ u_V)

        
        try:
            dc_analysis = simulator.dc(Vg=slice(0,1.2,0.05))  # Vg sweep
            # print("DC analysis completed successfully.")
            
           
            Id = -dc_analysis['Vd']
            Id_list.append(Id*1e6) #unit = uA
        except Exception as e:
            print(f"Error at Vd = {Vd_value} V: {e}")

    # 将 Id_list 转换为 NumPy 数组
    Id_list = np.array(Id_list)
    Id_lg_values = np.log10(Id_list)

    return Vg_values, Id_list,Id_lg_values

def run_tran(C_eq, xyce_command=r"C:\Program Files\Xyce_7.9\bin\Xyce.exe"):
    
    
    circuit = Circuit("BSIM-CMG buffer")

  
    circuit.include("C:/Users/y50046737/Desktop/Spice_cap/invD8_buffer/model/PexNMosModel.sp")
    circuit.include("C:/Users/y50046737/Desktop/Spice_cap/invD8_buffer/model/PexPMosModel.sp")
    
    circuit.include('C:/Users/y50046737/Desktop/Spice_cap/invD8_buffer/INVD8.sp')
    circuit.include('C:/Users/y50046737/Desktop/Spice_cap/invD8_buffer/INVD1.sp')

    
    circuit.V('DD', 'vdd', circuit.gnd, 0.7)
    circuit.V('SS', 'vss', circuit.gnd, 0)
    
  
    circuit.X('INV1', 'INVD8', 'IN', 'VDD', 'VSS', 'N1')
    circuit.X('INV2', 'INVD8', 'N1', 'VDD', 'VSS', 'OUT1')
    circuit.X('INV3', 'INVD8', 'OUT1', 'VDD', 'VSS', 'N2')
    circuit.X('INV4', 'INVD8', 'N2', 'VDD', 'VSS', 'OUT')
    circuit.C('eq', 'OUT', circuit.gnd, C_eq)
    # circuit.MOSFET('n', 'drain', 'gate', circuit.gnd, circuit.gnd, model='nmos1')
    
    VDD= 0.7
    circuit.PulseVoltageSource('IN', 'IN', circuit.gnd,
                            initial_value=0@u_V,
                            pulsed_value=VDD,
                            delay_time=0.1@u_ns,
                            rise_time=1@u_ps,
                            fall_time=1@u_ps,
                            pulse_width=1@u_ns,
                            period=2@u_ns)
   
    circuit.C('LOAD', 'OUT', circuit.gnd, 1e-24 @u_F)  # 1e-9 femtofarad
    

   
    simulator = circuit.simulator(
        simulator='xyce-parallel',
        temperature=27,
        nominal_temperature=27,
        xyce_command=xyce_command
    )

   
    analysis = simulator.transient(step_time=1 @ u_ps, end_time=0.3 @ u_ns)

    
    return analysis.time, analysis['OUT']




def run_tran_inv(C_eq, xyce_command=r"C:\Program Files\Xyce_7.9\bin\Xyce.exe"):
    
    
    circuit = Circuit("BSIM-CMG buffer")

  
    circuit.include("C:/Users/y50046737/Desktop/Spice_cap/invD8_buffer/model/PexNMosModel.sp")
    circuit.include("C:/Users/y50046737/Desktop/Spice_cap/invD8_buffer/model/PexPMosModel.sp")
    
    circuit.include('C:/Users/y50046737/Desktop/Spice_cap/invD8_buffer/INVD8.sp')
    circuit.include('C:/Users/y50046737/Desktop/Spice_cap/invD8_buffer/INVD1.sp')

    
    circuit.V('DD', 'vdd', circuit.gnd, 0.7)
    circuit.V('SS', 'vss', circuit.gnd, 0)
    
  
    circuit.X('INV1', 'INVD1', 'IN', 'VDD', 'VSS', 'N1')
    circuit.X('INV2', 'INVD1', 'N1', 'VDD', 'VSS', 'OUT1')
    circuit.X('INV3', 'INVD1', 'OUT1', 'VDD', 'VSS', 'N2')
    circuit.X('INV4', 'INVD1', 'N2', 'VDD', 'VSS', 'OUT')
    circuit.C('eq', 'OUT', circuit.gnd, C_eq)
    # circuit.MOSFET('n', 'drain', 'gate', circuit.gnd, circuit.gnd, model='nmos1')
    
    VDD= 0.7
    circuit.PulseVoltageSource('IN', 'IN', circuit.gnd,
                            initial_value=0@u_V,
                            pulsed_value=VDD,
                            delay_time=0.1@u_ns,
                            rise_time=1@u_ps,
                            fall_time=1@u_ps,
                            pulse_width=1@u_ns,
                            period=2@u_ns)
   
    circuit.C('LOAD', 'OUT', circuit.gnd, 1e-24 @u_F)  # 1e-9 femtofarad
    

   
    simulator = circuit.simulator(
        simulator='xyce-parallel',
        temperature=27,
        nominal_temperature=27,
        xyce_command=xyce_command
    )

   
    analysis = simulator.transient(step_time=1 @ u_ps, end_time=0.3 @ u_ns)

    
    return analysis.time, analysis['OUT']



