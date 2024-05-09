import matplotlib.pyplot as plt 
import pandas as pd
from scipy import stats
import numpy as np

plt.style.use('leostyle3.mplstyle')

data_all: dict = {"Vikt": [24550,2730,1830,1960,1201,1907,11900,25400,4550,5085,20300,6005,2260,2950,5200,18000,900,1120,19000], "Batterikapacitet": [264,20,16,20,12.7,17.3,150,300,40,40,237,64,23.4,28,141,282,6,9,282]}

df_all = pd.DataFrame(data=data_all)
df_ex = df_all.iloc[:8]
df_wl = df_all.iloc[8:]

dump_liten_vikt = 25000
dump_stor_vikt = 39000
hjul_stor_vikt = 32150
band_stor_vikt = 49400

def battery_capacity(data: pd.DataFrame) -> None:
    if data is df_all:
        setting = "(grävmaskin och hjullastare)"
    elif data is df_wl:
        setting = "(hjullastare)"
    elif data is df_ex:
        setting = "(grävmaskin)"
    else:
        raise Exception("No setting could be chosen")
    
    # Perform linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(data['Vikt'], data['Batterikapacitet'])

    # Use the slope and intercept values to get the best fit line
    line_x = np.linspace(min(data['Vikt']), max(data['Vikt']), 100)  # Generate 100 points for drawing the line
    line_y = slope * line_x + intercept

    dump_liten_batkap = dump_liten_vikt*slope+intercept
    dump_stor_batkap = dump_stor_vikt*slope+intercept
    hjul_stor_batkap = hjul_stor_vikt*slope+intercept
    band_stor_batkap = band_stor_vikt*slope+intercept

    if setting == "(grävmaskin och hjullastare)":
        print(f"{dump_liten_batkap=}\n{dump_stor_batkap=}")
    elif setting == "(hjullastare)":
        print(f"{hjul_stor_batkap=}")
    elif setting == "(grävmaskin)":
        print(f"{band_stor_batkap=}")
    else:
        raise Exception("No setting could be chosen")

    print(f'{slope=}\n{intercept=}\n{r_value=}')
    plt.plot(line_x, line_y, label=f'{slope:.4f}x + {intercept:.2f}', color="orange", linestyle="dashed")
    plt.scatter(data["Vikt"], data["Batterikapacitet"])
    plt.title(f"Batterikapacitet i förhållande till maskinvikt\n{setting}")
    plt.xlabel("Vikt [kg]")
    plt.ylabel("Batterikapacitet [kWh]")
    plt.ylim(bottom=0, top=320)
    plt.legend()
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    battery_capacity(df_ex)




