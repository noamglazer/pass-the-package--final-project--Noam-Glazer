__author__ = "Noam Glazer"

import socket
import threading
import random
import time

SERVER_IP = '0.0.0.0'
PORT = 55555

clients = {}
package_holder = None

game_state = "WAITING"
lobby_start_time = None
LOBBY_DURATION = 15
game_start_time = 0
game_timer_duration = 0
active_round_players = []

# 🔑 מפתח הצפנה סודי (חייב להיות זהה ללקוח)
SECRET_KEY = 42


def xor_cipher(text):
    """פונקציה המצפינה ומפענחת טקסט באמצעות צופן XOR פשוט"""
    return "".join(chr(ord(char) ^ SECRET_KEY) for char in text)


def broadcast(message):
    for client_socket in clients.values():
        try:
            client_socket.send(message.encode('utf-8'))
        except:
            pass


def broadcast_player_list():
    names_list = ",".join(clients.keys())
    message = f"PLAYERS~{names_list}!"
    for client_socket in clients.values():
        try:
            client_socket.send(message.encode('utf-8'))
        except:
            pass


def check_game_timer():
    global game_state, lobby_start_time, package_holder, game_start_time, game_timer_duration, active_round_players
    print("[SERVER] Timer thread is running...")

    while True:
        if game_state == "WAITING" and lobby_start_time is not None:
            elapsed_lobby = time.time() - lobby_start_time
            if elapsed_lobby >= LOBBY_DURATION:
                if len(clients) >= 2:
                    game_state = "PLAYING"
                    active_round_players = list(clients.keys())
                    package_holder = active_round_players[0]
                    print(f"[SERVER] Lobby time up! Game started. Active players: {active_round_players}")
                    broadcast(f"SEND_TS~{package_holder}!")

                    game_timer_duration = random.randint(15, 30)
                    game_start_time = time.time()
                else:
                    print("[SERVER] Lobby time up but not enough players. Resetting lobby timer.")
                    lobby_start_time = time.time()

        elif game_state == "PLAYING":
            elapsed_game = time.time() - game_start_time
            if elapsed_game >= game_timer_duration:
                print(f"\n*** [SERVER] BOOM! {package_holder} is ELIMINATED! ***")

                try:
                    clients[package_holder].send("GAMEOV~LOSE!".encode('utf-8'))
                except:
                    pass

                if package_holder in active_round_players:
                    active_round_players.remove(package_holder)

                if len(active_round_players) == 1:
                    winner = active_round_players[0]
                    print(f"🏆🏆🏆 [SERVER] WE HAVE A WINNER: {winner} 🏆🏆🏆")
                    try:
                        clients[winner].send("GAMEOV~WIN!".encode('utf-8'))
                    except:
                        pass

                    game_state = "WAITING"
                    lobby_start_time = None
                    package_holder = None
                    active_round_players = []

                else:
                    print(f"[SERVER] Round over. Remaining players: {active_round_players}")
                    package_holder = active_round_players[0]
                    broadcast(f"SEND_TS~{package_holder}!")

                    game_timer_duration = random.randint(15, 30)
                    game_start_time = time.time()
                    print(f"[SERVER] Next round started! Timer set to {game_timer_duration} seconds.")

        time.sleep(0.5)


def handle_client(client_socket):
    global package_holder, game_state, lobby_start_time, active_round_players
    username = None

    try:
        while True:
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                break

            if data.endswith('!'):
                data = data[:-1]
            else:
                continue

            parts = data.split('~')
            msg = parts[0]

            if msg == "LOG_IN":
                encrypted_username = parts[1]

                # 🔓 פענוח שם המשתמש שהתקבל מוצפן מהלקוח!
                username = xor_cipher(encrypted_username)

                if game_state == "PLAYING":
                    client_socket.send("001~Game already started!".encode('utf-8'))
                    return

                if username in clients:
                    client_socket.send("001~Username already taken!".encode('utf-8'))
                    return

                clients[username] = client_socket
                print(f"[SERVER] User '{username}' authenticated and joined the lobby.")

                broadcast_player_list()
                client_socket.send("LOG_IN~OK!".encode('utf-8'))

                if len(clients) == 1:
                    lobby_start_time = time.time()
                    print(f"[SERVER] First player joined. Lobby countdown started ({LOBBY_DURATION}s).")

            elif msg == "SEND_TO":
                target_player = parts[1]

                if username != package_holder:
                    client_socket.send("002~You do not have the package!".encode('utf-8'))
                    continue

                if target_player not in active_round_players:
                    client_socket.send("003~Target player not active in this round!".encode('utf-8'))
                    continue

                package_holder = target_player
                print(f"[SERVER] Package passed from {username} to {package_holder}")
                broadcast(f"SEND_TS~{package_holder}!")

    except Exception as e:
        print(f"[SERVER ERROR] {username}: {e}")
    finally:
        if username in clients:
            del clients[username]
            print(f"[SERVER] User '{username}' disconnected.")

            if username in active_round_players:
                active_round_players.remove(username)

            if package_holder == username:
                if active_round_players:
                    package_holder = active_round_players[0]
                    broadcast(f"SEND_TS~{package_holder}!")
                else:
                    package_holder = None
            broadcast_player_list()
        client_socket.close()


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((SERVER_IP, PORT))
    server.listen()
    print(f"[SERVER] Server is running on port {PORT}...")

    timer_thread = threading.Thread(target=check_game_timer)
    timer_thread.daemon = True
    timer_thread.start()

    while True:
        client_socket, client_address = server.accept()
        client_thread = threading.Thread(target=handle_client, args=(client_socket,))
        client_thread.start()


if __name__ == "__main__":
    start_server()