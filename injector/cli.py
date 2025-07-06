import click
from modules import latency
from modules import loss
from modules import interface as iface
from modules import dos


@click.group()
def cli():
    pass

@cli.command()
@click.option('--interface', default="eth0", help="Network interface to affect")
@click.option('--delay', default=200, help="Delay in milliseconds")
def inject_latency(interface, delay):
    """Inject latency on a network interface."""
    latency.add_latency(interface, delay)

@cli.command()
@click.option('--interface', default="eth0", help="Network interface to affect")
def clear(interface):
    """Clear all network faults from the interface."""
    latency.clear_latency(interface)


@cli.command()
@click.option('--interface', default="eth0", help="Network interface to affect")
@click.option('--loss', default=10, help="Packet loss percentage")
def inject_loss(interface, loss):
    """Inject packet loss on a network interface."""
    loss.add_packet_loss(interface, loss)

@cli.command()
@click.option('--interface', default="eth0", help="Network interface to affect")
def clear_loss(interface):
    """Clear packet loss on a network interface."""
    loss.clear_packet_loss(interface)


@cli.command()
@click.option('--interface', default="eth0", help="Network interface to bring down")
def down(interface):
    """Disable a network interface."""
    iface.bring_down(interface)

@cli.command()
@click.option('--interface', default="eth0", help="Network interface to bring up")
def up(interface):
    """Enable a network interface."""
    iface.bring_up(interface)

@cli.command()
@click.option('--interface', default="eth0", help="Network interface to restart")
@click.option('--downtime', default=5, help="Time (in seconds) to keep the interface down")
def restart(interface, downtime):
    """Temporarily bring interface down and back up."""
    iface.restart_interface(interface, downtime)


@cli.command()
@click.option('--target-ip', required=True, help="Target IP address")
@click.option('--port', default=80, help="Target port for SYN flood")
@click.option('--count', default=100, help="Number of SYN packets to send")
def syn_flood(target_ip, port, count):
    """Simulate SYN flood using Scapy"""
    dos.syn_flood(target_ip, port, count)

@cli.command()
@click.option('--target-ip', required=True, help="Target IP address")
@click.option('--count', default=100, help="Number of ICMP packets to send")
def icmp_flood(target_ip, count):
    """Simulate ICMP flood using Scapy"""
    dos.icmp_flood(target_ip, count)


if __name__ == "__main__":
    cli()
