import math


def analyze_dc(voltage_v, resistance_ohm):
    if not math.isfinite(voltage_v):
        raise ValueError("Voltage must be a finite number.")
    if not math.isfinite(resistance_ohm) or resistance_ohm <= 0:
        raise ValueError("Resistance must be a finite number greater than zero.")

    current_a = voltage_v / resistance_ohm
    power_w = voltage_v * current_a
    return {"current_a": current_a, "power_w": power_w}


def main():
    try:
        voltage_v = float(input("Enter voltage (V): "))
        resistance_ohm = float(input("Enter resistance (ohm): "))
        result = analyze_dc(voltage_v, resistance_ohm)
    except ValueError as error:
        print(f"Invalid input: {error}")
        return

    print(f"Current: {result['current_a']:.6g} A")
    print(f"Power: {result['power_w']:.6g} W")


if __name__ == "__main__":
    main()
    