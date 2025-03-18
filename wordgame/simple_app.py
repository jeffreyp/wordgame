import os
import random
import string
import time
import json
from collections import defaultdict
import nltk
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Download nltk dictionary if not already downloaded
nltk.download('words')
from nltk.corpus import words as nltk_words

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_key')

# Game state storage
games = {}
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

@app.route('/')
def index():
    return render_template('simple_index.html')

@app.route('/api/create_game', methods=['POST'])
def create_game():
    player_name = request.json.get('name', 'Player')
    
    # Create a unique room code
    while True:
        room_code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if room_code not in games:
            break
    
    # Initialize game
    games[room_code] = {
        'status': 'waiting',
        'grid': None,
        'round_end_time': None,
        'players': {
            1: {
                'name': player_name,
                'score': 0,
                'words': []
            }
        }
    }
    
    session['player_id'] = 1
    session['room_code'] = room_code
    
    return jsonify({
        'room_code': room_code,
        'player_id': 1
    })

@app.route('/api/join_game', methods=['POST'])
def join_game():
    data = request.json
    room_code = data.get('room_code', '').upper()
    player_name = data.get('name', 'Player')
    
    if room_code not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    game = games[room_code]
    
    if game['status'] != 'waiting':
        return jsonify({'error': 'Game already in progress'}), 400
    
    if len(game['players']) >= 2:
        return jsonify({'error': 'Game is full'}), 400
    
    # Add player to game
    player_id = 2  # Second player gets ID 2
    game['players'][player_id] = {
        'name': player_name,
        'score': 0,
        'words': []
    }
    
    session['player_id'] = player_id
    session['room_code'] = room_code
    
    # Start the game
    start_game(room_code)
    
    return jsonify({
        'room_code': room_code,
        'player_id': player_id,
        'players': [{'id': pid, 'name': pdata['name']} for pid, pdata in game['players'].items()]
    })

def start_game(room_code):
    game = games[room_code]
    game['status'] = 'playing'
    game['grid'] = generate_grid()
    game['round_end_time'] = time.time() + 120  # 120 seconds round (2 minutes)
    
    # Reset player scores and words
    for player in game['players'].values():
        player['score'] = 0
        player['words'] = []

@app.route('/api/game_status', methods=['GET'])
def game_status():
    room_code = session.get('room_code')
    player_id = session.get('player_id')
    
    if not room_code or not player_id or room_code not in games:
        return jsonify({'error': 'Not in a game'}), 400
    
    game = games[room_code]
    
    response = {
        'status': game['status'],
        'player_id': player_id,
        'players': game['players'],
    }
    
    if game['status'] in ['playing', 'finished']:
        response['grid'] = game['grid']
        
        if game['status'] == 'playing':
            response['end_time'] = game['round_end_time']
            
            # Check if time is up
            if time.time() > game['round_end_time'] and game['status'] == 'playing':
                process_game_end(room_code)
                response['status'] = 'finished'
                
    if game['status'] == 'finished':
        # Determine winner
        max_score = -1
        winners = []
        
        for pid, player_data in game['players'].items():
            if player_data['score'] > max_score:
                max_score = player_data['score']
                winners = [pid]
            elif player_data['score'] == max_score:
                winners.append(pid)
        
        response['winners'] = winners
    
    return jsonify(response)

@app.route('/api/submit_word', methods=['POST'])
def submit_word():
    room_code = session.get('room_code')
    player_id = session.get('player_id')
    word = request.json.get('word', '').lower()
    
    if not room_code or not player_id or room_code not in games:
        return jsonify({'error': 'Not in a game'}), 400
    
    game = games[room_code]
    
    if game['status'] != 'playing':
        return jsonify({'error': 'Game not in progress'}), 400
    
    if time.time() > game['round_end_time']:
        process_game_end(room_code)
        return jsonify({'error': 'Time is up'}), 400
    
    player = game['players'][player_id]
    
    # Check if word is already used by this player
    if word in player['words']:
        return jsonify({'valid': False, 'reason': 'Already used'})
    
    # Check if word is valid English
    if word not in english_words:
        return jsonify({'valid': False, 'reason': 'Not in dictionary'})
    
    # Check if word can be formed from the grid
    if not is_word_in_grid(word, game['grid']):
        return jsonify({'valid': False, 'reason': 'Cannot be formed from grid'})
    
    # Valid word, add to player's list and update score
    score = calculate_score(word)
    player['words'].append(word)
    player['score'] += score
    
    return jsonify({
        'valid': True,
        'word': word,
        'score': score,
        'total_score': player['score']
    })

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

@app.route('/api/restart_game', methods=['POST'])
def restart_game():
    room_code = session.get('room_code')
    player_id = session.get('player_id')
    
    if not room_code or not player_id or room_code not in games:
        return jsonify({'error': 'Not in a game'}), 400
    
    game = games[room_code]
    
    if game['status'] != 'finished':
        return jsonify({'error': 'Cannot restart - game not finished'}), 400
    
    # Reset game state
    start_game(room_code)
    
    return jsonify({'status': 'restarted'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 4000))
    app.run(host='0.0.0.0', port=port, debug=True)