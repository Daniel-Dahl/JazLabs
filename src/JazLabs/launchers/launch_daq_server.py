#!/usr/bin/env python3
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import get_named_config, load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(description="Run one configured JazLabs DAQ server.")
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--name", "--daq", dest="name", required=True)
    parser.add_argument("--host", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    parser.add_argument("--voltage-pub-port", type=int, default=None)
    parser.add_argument("--voltage-topic", default=None)
    parser.add_argument(
        "--daq-type",
        choices=("ni_daq", "mcc_daq", "coremorrow_daq"),
        default=None,
    )
    parser.add_argument("--device-num", type=int, default=None)
    parser.add_argument("--channel-count", type=int, default=None)
    parser.add_argument("--voltage-min", type=float, default=None)
    parser.add_argument("--voltage-max", type=float, default=None)
    parser.add_argument("--refresh-time", type=float, default=None)
    parser.add_argument("--serial-port", default=None)
    parser.add_argument(
        "--publish-voltages-over-zmq",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    return parser


def build_daq_kwargs(server_config):
    daq_kwargs = {
        "deviceNum": server_config["device_num"],
        "RefreshTime": server_config["refresh_time"],
    }

    if server_config["daq_type"] == "coremorrow_daq":
        daq_kwargs["voltage_min"] = server_config["voltage_min"]
        daq_kwargs["voltage_max"] = server_config["voltage_max"]
        if server_config.get("serial_port") is not None:
            daq_kwargs["port"] = server_config["serial_port"]

    return daq_kwargs


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    daq_config = get_named_config(config, "DAQ_SERVERS", args.name)
    daq = merge_overrides(
        daq_config,
        {
            "host": args.host,
            "command_port": args.command_port,
            "voltage_pub_port": args.voltage_pub_port,
            "voltage_topic": args.voltage_topic,
            "daq_type": args.daq_type,
            "device_num": args.device_num,
            "channel_count": args.channel_count,
            "voltage_min": args.voltage_min,
            "voltage_max": args.voltage_max,
            "refresh_time": args.refresh_time,
            "serial_port": args.serial_port,
            "publish_voltages_over_zmq": args.publish_voltages_over_zmq,
        },
    )

    mp.freeze_support()

    from JazLabs.hardware.DAQ_Controller.DAQ_stack.DAQ_Server import DAQZMQServer

    server = DAQZMQServer(
        host=daq["host"],
        command_port=daq["command_port"],
        voltage_pub_port=daq["voltage_pub_port"],
        DAQType=daq["daq_type"],
        DAQKwargs=build_daq_kwargs(daq),
        ChannelCount=daq["channel_count"],
        voltage_min=daq["voltage_min"],
        voltage_max=daq["voltage_max"],
        PublishVoltagesOverZMQ=daq["publish_voltages_over_zmq"],
        voltage_topic=daq["voltage_topic"],
    )

    print(f"Launching DAQ server {daq['name']!r}.")
    print(f"Host: {daq['host']}")
    print(f"Command port: {daq['command_port']}")
    print(f"Voltage PUB port: {daq['voltage_pub_port']}")
    print(f"Voltage topic: {daq['voltage_topic']}")
    print(f"DAQ type: {daq['daq_type']}")
    print(f"Device number: {daq['device_num']}")
    print(f"Channel count: {daq['channel_count']}")
    print(f"Voltage limits: {daq['voltage_min']} V to {daq['voltage_max']} V")
    print(f"Refresh time: {daq['refresh_time']}")
    print(f"Publish voltages over ZMQ: {daq['publish_voltages_over_zmq']}")
    if daq.get("serial_port") is not None:
        print(f"Serial port: {daq['serial_port']}")
    server.run_forever()


if __name__ == "__main__":
    main()
