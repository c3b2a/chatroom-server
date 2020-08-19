import socket
import sys
import time
import re
import base64
from uuid import uuid4 as uuid
from threading import Thread

host = '0.0.0.0'
port = 8000

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((host, port))

server_socket.listen(20)

rooms = {}
socket_connected = {}

ip_frequency_limit = {}

def chk_ip_frequency(ip):
	if ip in ip_frequency_limit:
		if ip_frequency_limit[ip][0] >= 10:
			return False
		else:
			ip_frequency_limit[ip][0] += 1
			return True
	else:
		ip_frequency_limit[ip] = [1, time.time()]
		return True

def ip_limit_reset():
	while True:
		del_list = []
		for ip, info in ip_frequency_limit.items():
			if time.time() - info[1] > 3600:
				del_list.append(ip)
		for ip in del_list:
			del ip_frequency_limit[ip]
		time.sleep(0.01)

def room_timeout():
	while True:
		del_list = []
		for room_id, create_time in rooms.items():
			if time.time() - create_time > 3600:
				del_list.append(room_id)
		for room_id in del_list:
			del rooms[room_id]
			del socket_connected[room_id]
		if len(del_list) != 0:
			print('delete rooms: ' + ', '.join(del_list))
		time.sleep(0.01)

def join_room(client, room_id):
	if room_id in socket_connected:
		repeated = False
		for c in socket_connected[room_id]:
			if c == client:
				repeated = True
		if not repeated:
			socket_connected[room_id].append(client)
			return True
		else:
			return False
	else:
		socket_connected[room_id] = [client, ]
		return True

def quit_room(client, room_id):
	if room_id in socket_connected:
		for i in range(len(socket_connected[room_id])):
			if socket_connected[room_id][i] == client:
				del socket_connected[room_id][i]
				break

def after_disconnect(client):
	for clients in socket_connected.values():
		for i in range(len(clients)):
			if clients[i] == client:
				del clients[i]
				break

def client_command(client, ip):
	print(ip + ': connected')
	start_time = time.time()
	while True:
		recv_data = client.recv(1024)
		recv_data = recv_data.decode()
		each_command = recv_data.split(';')
		for cmd in each_command:
			if len(cmd.split()) > 0:
				start_time = time.time()
				recv_command = cmd.split()
				if recv_command[0] != 'alive': print(ip + ': ' + ' '.join(recv_command))
				if recv_command[0] == 'new':
					avail = chk_ip_frequency(ip)
					if avail:
						room_id = str(uuid())
						rooms[room_id] = time.time()
						client.send(('new ' + room_id).encode())
					else:
						client.send('new -1'.encode())
				elif recv_command[0] == 'del':
					if len(recv_command) != 2:
						client.send('del -1'.encode())
					else:
						if recv_command[1] in rooms:
							del rooms[recv_command[1]]
							del socket_connected[recv_command[1]]
							client.send('del 1'.encode())
						else:
							client.send('del 0'.encode())
				elif recv_command[0] == 'join':
					if len(recv_command) != 2:
						client.send('join -1'.encode())
					else:
						if recv_command[1] in rooms:
							avail = join_room(client, recv_command[1])
							if avail:
								client.send(('join 1 ' + recv_command[1]).encode())
							else:
								client.send('join 0'.encode())
						else:
							client.send('join 0'.encode())
				elif recv_command[0] == 'join_without_return':
					if len(recv_command) == 2 and recv_command[1] in rooms:
						join_room(client, recv_command[1])
				elif recv_command[0] == 'quit':
					if len(recv_command) != 2:
						client.send('quit -1'.encode())
					else:
						if recv_command[1] in rooms:
							quit_room(client, recv_command[1])
							client.send('quit 1'.encode())
						else:
							client.send('quit 0'.encode())
				elif recv_command[0] == 'quit_without_return':
					if len(recv_command) == 2:
						if recv_command[1] in rooms:
							quit_room(client, recv_command[1])
				elif recv_command[0] == 'send':
					if len(recv_command) != 4:
						client.send('send -1'.encode())
					else:
						room_id = recv_command[1]
						username = recv_command[2]
						send_msg = recv_command[3]
						for room, clients in socket_connected.items():
							if room == room_id:
								for c in clients:
									c.send(('msg ' + room_id + ' ' + username + ' ' + send_msg).encode())
		if time.time() - start_time > 10:
			break
		time.sleep(0.01)
	after_disconnect(client)
	client.close()
	print(ip + ': disconnected')

room_clean = Thread(target = room_timeout)
room_clean.start()
ip_limit_clean = Thread(target = ip_limit_reset)
ip_limit_clean.start()

while True:
	client, addr = server_socket.accept()
	thread = Thread(target = client_command, args = (client, addr[0]))
	thread.start()

server_socket.close()
