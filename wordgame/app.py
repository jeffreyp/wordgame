import os
import random
import string
import time
from collections import defaultdict
import nltk
from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Download nltk dictionary if not already downloaded
nltk.download('words')
from nltk.corpus import words as nltk_words

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_key')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=None)

# Game state storage
games = {}
player_rooms = {}
english_words = set(word.lower() for word in nltk_words.words() if len(word) >= 3)

def generate_grid(size=4):
    """Generate a random grid of letters with no duplicates"""
    # Include more vowels to make grid more playable
    vowels = 'aeiou'
    consonants = ''.join(c for c in string.ascii_lowercase if c not in vowels)
    
    # Create a list of all available letters
    all_letters = list(string.ascii_lowercase)
    
    # Select unique letters with preference for vowels
    letters = []
    # Target number of vowels (about 40% of the grid)
    vowel_count = int(size*size*0.4)
    
    # First select vowels
    available_vowels = [c for c in all_letters if c in vowels]
    random.shuffle(available_vowels)
    letters.extend(available_vowels[:vowel_count])
    
    # Remove selected vowels from available letters
    for letter in letters:
        all_letters.remove(letter)
    
    # Fill remaining spaces with consonants or other letters
    random.shuffle(all_letters)
    letters.extend(all_letters[:size*size - len(letters)])
    
    # Shuffle and reshape into grid
    random.shuffle(letters)
    grid = []
    for i in range(0, size*size, size):
        grid.append(letters[i:i+size])
    
    return grid

def calculate_score(word):
    """Calculate word score - longer words are worth more points"""
    length = len(word)
    if length <= 3:
        return 1
    elif length == 4:
        return 2
    elif length == 5:
        return 4
    elif length == 6:
        return 6
    elif length == 7:
        return 8
    else:
        return 10

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    player_id = request.sid
    if player_id in player_rooms:
        room = player_rooms[player_id]
        leave_room(room)
        
        if room in games:
            game = games[room]
            if player_id in game['players']:
                player_name = game['players'][player_id]['name']
                emit('player_left', {'player_id': player_id, 'name': player_name}, to=room)
                
                # If game is in progress, end it
                if game['status'] == 'playing':
                    game['status'] = 'finished'
                    emit('game_ended', {'reason': 'Player disconnected'}, to=room)
                
                # Remove player from game
                del game['players'][player_id]
                
                # If all players left, remove the game
                if not game['players']:
                    del games[room]
        
        del player_rooms[player_id]

@socketio.on('create_game')
def handle_create_game(data):
    player_id = request.sid
    player_name = data.get('name', f"Player_{player_id[:4]}")
    
    # Create a unique room code
    while True:
        room_code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if room_code not in games:
            break
    
    # Store room for player
    player_rooms[player_id] = room_code
    join_room(room_code)
    
    # Initialize game
    games[room_code] = {
        'status': 'waiting',
        'grid': None,
        'round_end_time': None,
        'players': {
            player_id: {
                'name': player_name,
                'score': 0,
                'words': []
            }
        }
    }
    
    emit('game_created', {'room_code': room_code, 'player_id': player_id})
    emit('player_joined', {'player_id': player_id, 'name': player_name}, to=room_code)

@socketio.on('join_game')
def handle_join_game(data):
    player_id = request.sid
    room_code = data.get('room_code', '').upper()
    player_name = data.get('name', f"Player_{player_id[:4]}")
    
    if room_code not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game = games[room_code]
    
    if game['status'] != 'waiting':
        emit('error', {'message': 'Game already in progress'})
        return
    
    if len(game['players']) >= 2:
        emit('error', {'message': 'Game is full'})
        return
    
    # Store room for player
    player_rooms[player_id] = room_code
    join_room(room_code)
    
    # Add player to game
    game['players'][player_id] = {
        'name': player_name,
        'score': 0,
        'words': []
    }
    
    emit('game_joined', {
        'room_code': room_code, 
        'player_id': player_id,
        'players': [{'id': pid, 'name': pdata['name']} for pid, pdata in game['players'].items()]
    })
    
    emit('player_joined', {'player_id': player_id, 'name': player_name}, to=room_code)
    
    # If two players joined, start the game
    if len(game['players']) == 2:
        start_game(room_code)

def start_game(room_code):
    game = games[room_code]
    game['status'] = 'playing'
    game['grid'] = generate_grid()
    game['round_end_time'] = time.time() + 120  # 120 seconds round (2 minutes)
    
    # Reset player scores and words
    for player in game['players'].values():
        player['score'] = 0
        player['words'] = []
    
    # Send game start event with grid
    socketio.emit('game_started', {
        'grid': game['grid'],
        'end_time': game['round_end_time']
    }, to=room_code)
    
    # Schedule game end
    socketio.start_background_task(end_game_after_timeout, room_code)

def end_game_after_timeout(room_code):
    if room_code not in games:
        return
    
    game = games[room_code]
    seconds_left = game['round_end_time'] - time.time()
    
    if seconds_left > 0:
        socketio.sleep(seconds_left)
    
    # Check if game still exists and is in progress
    if room_code in games and games[room_code]['status'] == 'playing':
        process_game_end(room_code)

def process_game_end(room_code):
    game = games[room_code]
    game['status'] = 'finished'
    
    # Calculate final scores
    word_owners = defaultdict(list)
    for player_id, player_data in game['players'].items():
        for word in player_data['words']:
            word_owners[word].append(player_id)
    
    # Words found by more than one player are removed
    for word, owners in word_owners.items():
        if len(owners) > 1:
            for player_id in owners:
                if word in game['players'][player_id]['words']:
                    game['players'][player_id]['words'].remove(word)
                    # Subtract points
                    game['players'][player_id]['score'] -= calculate_score(word)
    
    # Determine winner
    max_score = -1
    winners = []
    
    for player_id, player_data in game['players'].items():
        if player_data['score'] > max_score:
            max_score = player_data['score']
            winners = [player_id]
        elif player_data['score'] == max_score:
            winners.append(player_id)
    
    # Send results
    socketio.emit('game_ended', {
        'players': game['players'],
        'winners': winners
    }, to=room_code)

@socketio.on('submit_word')
def handle_submit_word(data):
    player_id = request.sid
    word = data.get('word', '').lower()
    
    if player_id not in player_rooms:
        emit('error', {'message': 'Not in a game'})
        return
    
    room_code = player_rooms[player_id]
    
    if room_code not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game = games[room_code]
    
    if game['status'] != 'playing':
        emit('error', {'message': 'Game not in progress'})
        return
    
    if time.time() > game['round_end_time']:
        emit('error', {'message': 'Time is up'})
        return
    
    player = game['players'][player_id]
    
    # Check if word is already used by this player
    if word in player['words']:
        emit('word_result', {'word': word, 'valid': False, 'reason': 'Already used'})
        return
    
    # Check if word is valid English
    if word not in english_words:
        emit('word_result', {'word': word, 'valid': False, 'reason': 'Not in dictionary'})
        return
    
    # Check if word can be formed from the grid
    if not is_word_in_grid(word, game['grid']):
        emit('word_result', {'word': word, 'valid': False, 'reason': 'Cannot be formed from grid'})
        return
    
    # Valid word, add to player's list and update score
    score = calculate_score(word)
    player['words'].append(word)
    player['score'] += score
    
    emit('word_result', {
        'word': word, 
        'valid': True, 
        'score': score,
        'total_score': player['score']
    })
    
    # Notify other players (but don't reveal the word)
    emit('opponent_found_word', {
        'player_id': player_id,
        'name': player['name'],
        'word_length': len(word),
        'score': player['score']
    }, to=room_code, include_self=False)

def is_word_in_grid(word, grid):
    """Check if word can be formed from adjacent letters in the grid"""
    size = len(grid)
    word = word.lower()
    
    # Helper function to find all occurrences of the first letter
    def find_starting_positions(letter):
        positions = []
        for i in range(size):
            for j in range(size):
                if grid[i][j] == letter:
                    positions.append((i, j))
        return positions
    
    # Helper function to check if we can form the word starting at position
    def search_from_position(pos, remaining, used_positions):
        row, col = pos
        
        # If we've used all letters, we found the word
        if not remaining:
            return True
        
        # Get the next letter to find
        next_letter = remaining[0]
        
        # Check all adjacent cells
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                # Skip the current cell
                if dr == 0 and dc == 0:
                    continue
                
                # Calculate neighbor position
                new_row, new_col = row + dr, col + dc
                
                # Check if the position is valid, has the right letter, and hasn't been used
                if (0 <= new_row < size and 0 <= new_col < size and 
                    grid[new_row][new_col] == next_letter and 
                    (new_row, new_col) not in used_positions):
                    
                    # Try this path
                    if search_from_position(
                        (new_row, new_col), 
                        remaining[1:], 
                        used_positions + [(new_row, new_col)]):
                        return True
        
        # If we get here, no path worked
        return False
    
    # Try each possible starting position
    start_positions = find_starting_positions(word[0])
    for pos in start_positions:
        if search_from_position(pos, word[1:], [pos]):
            return True
    
    # If we get here, no valid path was found
    return False

@socketio.on('restart_game')
def handle_restart_game(data):
    player_id = request.sid
    
    if player_id not in player_rooms:
        emit('error', {'message': 'Not in a game'})
        return
    
    room_code = player_rooms[player_id]
    
    if room_code not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game = games[room_code]
    
    if game['status'] != 'finished':
        emit('error', {'message': 'Cannot restart - game not finished'})
        return
    
    # Reset game state
    start_game(room_code)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    # Use standard Flask run method instead of socketio.run for better compatibility
    app.run(host='0.0.0.0', port=port, debug=True)