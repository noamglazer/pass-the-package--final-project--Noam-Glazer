__author__ = "Noam Glazer"

import socket
import threading
import sys
import pygame
import math

SERVER_IP = '127.0.0.1'
PORT = 55555
current_holder = None
my_username = ""
game_running = True
players = []
game_result = None

# 🔑 מפתח הצפנה סודי (חייב להיות זהה בלקוח ובשרת)
SECRET_KEY = 42


def xor_cipher(text):
    """פונקציה המצפינה ומפענחת טקסט באמצעות צופן XOR פשוט"""
    return "".join(chr(ord(char) ^ SECRET_KEY) for char in text)


def receive_messages(client_socket):
    global current_holder, game_running, players, game_result
    try:
        while True:
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                break

            if data.endswith('!'):
                data = data[:-1]

            parts = data.split('~')
            msg = parts[0]

            if msg == "LOG_IN" and parts[1] == "OK":
                print("\n[CLIENT] Login successful!")
            elif msg == "001":
                print(f"\n[SERVER ERROR] {parts[1]}")
                # אם יש שגיאה בהתחברות (שם תפוס למשל), ננקה את השם כדי שהמסך יאפשר לנסות שוב
                my_username = ""
                break

            elif msg == "SEND_TS":
                # השרת שולח שם מפוענח, פשוט מעדכנים
                current_holder = parts[1]

            elif msg == "PLAYERS":
                raw_names = parts[1]
                players = raw_names.split(',')

            elif msg == "GAMEOV":
                game_result = parts[1]
                print(f"\n[GAME OVER] You {game_result}!")

            elif msg in ["002", "003"]:
                print(f"\n[GAME ERROR] {parts[1]}")

    except Exception as e:
        print(f"\n[CLIENT ERROR] {e}")
    finally:
        client_socket.close()
        sys.exit()


def draw_players(screen, font):
    global players, current_holder
    if not players:
        return {}

    center_x, center_y = 400, 300
    radius = 180
    player_positions = {}
    num_players = len(players)

    for index, player_name in enumerate(players):
        angle = index * (2 * math.pi / num_players)
        x = int(center_x + radius * math.cos(angle))
        y = int(center_y + radius * math.sin(angle))
        player_positions[player_name] = (x, y)

        if current_holder is not None and player_name == current_holder:
            pygame.draw.circle(screen, (255, 215, 0), (x, y), 45)

        pygame.draw.circle(screen, (0, 120, 255), (x, y), 35)
        name_surface = font.render(player_name, True, (255, 255, 255))
        screen.blit(name_surface, (x - name_surface.get_width() // 2, y - 65))

    return player_positions


def start_client():
    global my_username, game_running, players, game_result, current_holder
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client_socket.connect((SERVER_IP, PORT))
    except Exception as e:
        print(f"Could not connect to server: {e}")
        return

    # אתחול Pygame מוקדם כדי להציג את מסך ההתחברות
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Pass the Package - Connection")

    font = pygame.font.SysFont("Arial", 30)
    big_font = pygame.font.SysFont("Arial", 45, bold=True)
    clock = pygame.time.Clock()

    input_text = ""
    logged_in = False

    # 🚪 --- שלב א': מסך התחברות גרפי ב-Pygame ---
    while not logged_in and game_running:
        screen.fill((30, 30, 40))  # רקע כהה למסך הפתיחה

        title_text = big_font.render("PASS THE PACKAGE", True, (255, 215, 0))
        prompt_text = font.render("Enter your username and press ENTER:", True, (200, 200, 200))

        screen.blit(title_text, (400 - title_text.get_width() // 2, 150))
        screen.blit(prompt_text, (400 - prompt_text.get_width() // 2, 250))

        # ציור תיבת הקלט
        input_box = pygame.Rect(250, 320, 300, 50)
        pygame.draw.rect(screen, (50, 50, 60), input_box)
        pygame.draw.rect(screen, (0, 120, 255), input_box, 2)  # מסגרת כחולה

        # הצגת הטקסט שהוקלד בתוך התיבה
        text_surface = font.render(input_text, True, (255, 255, 255))
        screen.blit(text_surface, (input_box.x + 10, input_box.y + 10))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game_running = False
                pygame.quit()
                client_socket.close()
                sys.exit()

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:  # לחיצה על Enter
                    if input_text.strip() != "":
                        my_username = input_text.strip()

                        # 🔒 הצפנת שם המשתמש לפני השליחה!
                        encrypted_username = xor_cipher(my_username)
                        client_socket.send(f"LOG_IN~{encrypted_username}!".encode('utf-8'))

                        logged_in = True
                elif event.key == pygame.K_BACKSPACE:  # מחיקת אות
                    input_text = input_text[:-1]
                else:
                    # הוספת האות שהוקלדה (הגבלה ל-15 תווים כדי שלא ייצא מהקופסה)
                    if len(input_text) < 15 and event.unicode.isprintable():
                        input_text += event.unicode

        pygame.display.flip()
        clock.tick(60)

    # שינוי כותרת החלון לאחר התחברות מוצלחת
    pygame.display.set_caption(f"Pass the Package - {my_username}")

    # הפעלת ה-Thread שמקשיב לשרת (רק אחרי ששלחנו את בקשת ההתחברות)
    recv_thread = threading.Thread(target=receive_messages, args=(client_socket,))
    recv_thread.daemon = True
    recv_thread.start()

    active_positions = {}

    # 🎮 --- שלב ב': לולאת המשחק הראשית (לובי + משחק) ---
    while game_running:
        if game_result is not None:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    game_running = False

            if game_result == "WIN":
                screen.fill((0, 150, 0))
                end_text = big_font.render("YOU WIN! 🏆", True, (255, 255, 255))
            else:
                screen.fill((150, 0, 0))
                end_text = big_font.render("BOOM! YOU LOSE... 💥", True, (255, 255, 255))

            screen.blit(end_text, (400 - end_text.get_width() // 2, 300 - end_text.get_height() // 2))
            pygame.display.flip()
            clock.tick(60)
            continue

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game_running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and current_holder is not None:
                    mouse_x, mouse_y = event.pos
                    for player_name, pos in active_positions.items():
                        if player_name != my_username:
                            target_x, target_y = pos
                            distance = math.sqrt((mouse_x - target_x) ** 2 + (mouse_y - target_y) ** 2)
                            if distance <= 35:
                                print(f"[CLIENT] Sending package to {player_name}")
                                client_socket.send(f"SEND_TO~{player_name}!".encode('utf-8'))
                                break

        if current_holder is None:
            screen.fill((40, 50, 70))
            msg_text = big_font.render("LOBBY - Waiting for game...", True, (255, 255, 255))
        elif current_holder == my_username:
            screen.fill((200, 0, 0))
            msg_text = big_font.render("YOU HAVE THE PACKAGE!", True, (255, 255, 255))
        else:
            screen.fill((50, 50, 50))
            msg_text = font.render(f"Holding: {current_holder}", True, (255, 255, 0))

        active_positions = draw_players(screen, font)

        my_name_text = font.render(f"Me: {my_username}", True, (200, 200, 200))
        screen.blit(my_name_text, (20, 20))
        screen.blit(msg_text, (400 - msg_text.get_width() // 2, 300 - msg_text.get_height() // 2))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    client_socket.close()


if __name__ == "__main__":
    start_client()