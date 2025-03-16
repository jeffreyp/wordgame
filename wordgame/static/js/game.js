document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    let playerId = null;
    let roomCode = null;
    let gameGrid = null;
    let timerInterval = null;
    let foundWords = new Set();

    // DOM elements
    const welcomeScreen = document.getElementById('welcome-screen');
    const createGameBtn = document.getElementById('create-game');
    const joinGameBtn = document.getElementById('join-game');
    const joinRoomInput = document.getElementById('join-room-code');
    const playerNameInput = document.getElementById('player-name');
    const waitingScreen = document.getElementById('waiting-screen');
    const roomCodeDisplay = document.getElementById('room-code-display');
    const playersWaiting = document.getElementById('players-waiting');
    const gameScreen = document.getElementById('game-screen');
    const gridContainer = document.getElementById('grid-container');
    const wordInput = document.getElementById('word-input');
    const submitWordBtn = document.getElementById('submit-word');
    const playerScore = document.getElementById('player-score');
    const opponentScore = document.getElementById('opponent-score');
    const foundWordsList = document.getElementById('found-words');
    const timer = document.getElementById('timer');
    const gameOverScreen = document.getElementById('game-over-screen');
    const gameResults = document.getElementById('game-results');
    const playAgainBtn = document.getElementById('play-again');
    const gameMessage = document.getElementById('game-message');

    // Show welcome screen initially
    showScreen(welcomeScreen);

    // Event listeners
    createGameBtn.addEventListener('click', () => {
        const playerName = playerNameInput.value.trim() || 'Player';
        socket.emit('create_game', { name: playerName });
    });

    joinGameBtn.addEventListener('click', () => {
        const roomCode = joinRoomInput.value.trim().toUpperCase();
        const playerName = playerNameInput.value.trim() || 'Player';
        
        if (roomCode) {
            socket.emit('join_game', { room_code: roomCode, name: playerName });
        } else {
            showMessage('Please enter a valid room code', 'error');
        }
    });

    submitWordBtn.addEventListener('click', submitWord);
    wordInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            submitWord();
        }
    });

    playAgainBtn.addEventListener('click', () => {
        socket.emit('restart_game', {});
    });

    // Socket event handlers
    socket.on('connect', () => {
        console.log('Connected to server');
    });

    socket.on('error', (data) => {
        showMessage(data.message, 'error');
    });

    socket.on('game_created', (data) => {
        playerId = data.player_id;
        roomCode = data.room_code;
        roomCodeDisplay.textContent = roomCode;
        showScreen(waitingScreen);
    });

    socket.on('game_joined', (data) => {
        playerId = data.player_id;
        roomCode = data.room_code;
        roomCodeDisplay.textContent = roomCode;
        
        // Update players list
        updatePlayersList(data.players);
        
        showScreen(waitingScreen);
    });

    socket.on('player_joined', (data) => {
        const playerItem = document.createElement('div');
        playerItem.classList.add('player-item');
        playerItem.id = `player-${data.player_id}`;
        playerItem.textContent = data.name;
        playersWaiting.appendChild(playerItem);

        // Display notification
        showMessage(`${data.name} joined the game`, 'info');
    });

    socket.on('player_left', (data) => {
        const playerItem = document.getElementById(`player-${data.player_id}`);
        if (playerItem) {
            playersWaiting.removeChild(playerItem);
        }

        showMessage(`${data.name} left the game`, 'info');
    });

    socket.on('game_started', (data) => {
        gameGrid = data.grid;
        createGameGrid(gameGrid);
        resetGameState();
        startTimer(Math.floor(data.end_time - (Date.now() / 1000)));
        showScreen(gameScreen);
    });

    socket.on('word_result', (data) => {
        if (data.valid) {
            foundWords.add(data.word);
            playerScore.textContent = data.total_score;
            
            // Add word to list
            const wordItem = document.createElement('li');
            wordItem.textContent = `${data.word} (+${data.score})`;
            foundWordsList.appendChild(wordItem);
            
            showMessage(`Found "${data.word}" for ${data.score} points!`, 'success');
        } else {
            showMessage(`Invalid word: ${data.reason}`, 'error');
        }
        
        wordInput.value = '';
        wordInput.focus();
    });

    socket.on('opponent_found_word', (data) => {
        opponentScore.textContent = data.score;
        showMessage(`${data.name} found a ${data.word_length}-letter word`, 'info');
    });

    socket.on('game_ended', (data) => {
        clearInterval(timerInterval);
        
        if (data.reason) {
            showMessage(data.reason, 'info');
            return;
        }
        
        // Generate results HTML
        let resultsHTML = '<h3>Game Results</h3>';
        
        for (const [id, player] of Object.entries(data.players)) {
            const isYou = id === playerId;
            const isWinner = data.winners.includes(id);
            
            resultsHTML += `<div class="player-result ${isYou ? 'you' : ''} ${isWinner ? 'winner' : ''}">`;
            resultsHTML += `<h4>${player.name} ${isYou ? '(You)' : ''} ${isWinner ? '🏆' : ''}</h4>`;
            resultsHTML += `<p>Score: ${player.score}</p>`;
            
            if (player.words.length > 0) {
                resultsHTML += '<p>Words found:</p><ul>';
                player.words.forEach(word => {
                    resultsHTML += `<li>${word}</li>`;
                });
                resultsHTML += '</ul>';
            } else {
                resultsHTML += '<p>No words found</p>';
            }
            
            resultsHTML += '</div>';
        }
        
        // Set results and show game over screen
        gameResults.innerHTML = resultsHTML;
        showScreen(gameOverScreen);
    });

    // Helper functions
    function showScreen(screen) {
        // Hide all screens
        [welcomeScreen, waitingScreen, gameScreen, gameOverScreen].forEach(s => {
            s.style.display = 'none';
        });
        
        // Show the requested screen
        screen.style.display = 'block';
    }

    function updatePlayersList(players) {
        playersWaiting.innerHTML = '';
        
        players.forEach(player => {
            const playerItem = document.createElement('div');
            playerItem.classList.add('player-item');
            playerItem.id = `player-${player.id}`;
            playerItem.textContent = player.name;
            playersWaiting.appendChild(playerItem);
        });
    }

    function createGameGrid(grid) {
        gridContainer.innerHTML = '';
        
        for (let i = 0; i < grid.length; i++) {
            for (let j = 0; j < grid[i].length; j++) {
                const cell = document.createElement('div');
                cell.classList.add('grid-cell');
                cell.textContent = grid[i][j].toUpperCase();
                gridContainer.appendChild(cell);
            }
        }
    }

    function resetGameState() {
        foundWords.clear();
        foundWordsList.innerHTML = '';
        playerScore.textContent = '0';
        opponentScore.textContent = '0';
        wordInput.value = '';
    }

    function startTimer(seconds) {
        let timeLeft = Math.floor(seconds);
        
        timer.textContent = formatTime(timeLeft);
        
        clearInterval(timerInterval);
        timerInterval = setInterval(() => {
            timeLeft--;
            
            if (timeLeft < 0) {
                clearInterval(timerInterval);
                return;
            }
            
            timer.textContent = formatTime(timeLeft);
            
            if (timeLeft <= 10) {
                timer.classList.add('urgent');
            }
        }, 1000);
    }

    function formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    function submitWord() {
        const word = wordInput.value.trim().toLowerCase();
        
        if (word.length >= 3) {
            socket.emit('submit_word', { word });
        } else {
            showMessage('Word must be at least 3 letters', 'error');
        }
    }

    function showMessage(text, type = 'info') {
        gameMessage.textContent = text;
        gameMessage.className = `message ${type}`;
        
        // Clear message after 3 seconds
        setTimeout(() => {
            gameMessage.textContent = '';
        }, 3000);
    }
});
