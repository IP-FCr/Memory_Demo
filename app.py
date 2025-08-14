import streamlit as st
import random
import base64
import json
from typing import List, Dict, Any
import streamlit.components.v1 as components

# --------------- Utilities ---------------

def _rerun():
    # Compatibility shim across Streamlit versions
    try:
        st.rerun()
    except AttributeError:
        # Older versions
        st.experimental_rerun()

def _init_state():
    ss = st.session_state
    ss.setdefault("stage", "setup")  # "setup" | "pair" | "play" | "win"
    ss.setdefault("back_img", None)  # bytes
    ss.setdefault("faces", [])       # list of dicts: {id, name, bytes}
    ss.setdefault("unpaired_ids", set())  # Set[int]
    ss.setdefault("pair_bucket", [])      # List[int] (0..2)
    ss.setdefault("pairs", [])            # List[List[int]] -> [[id1, id2], ...]
    ss.setdefault("deck", [])             # List[Dict]
    ss.setdefault("revealed", [])         # List[int] (card positions)
    ss.setdefault("mismatch_pending", False)
    ss.setdefault("cols", 4)
    ss.setdefault("size_px", 160)
    ss.setdefault("card_spacing", 10)     # Added: spacing between cards
    ss.setdefault("game_won", False)      # Track win state
    ss.setdefault("container_scale", 100) # Container scale percentage


def _chunk(lst: List[Any], n: int) -> List[List[Any]]:
    '''Split iterable into consecutive chunks of size n.'''
    return [lst[i:i+n] for i in range(0, len(lst), n)]


def _face_lookup() -> Dict[int, Dict[str, Any]]:
    '''Return face dict by id for quick lookup.'''
    return {f["id"]: f for f in st.session_state.faces}


def _image_to_base64(image_bytes):
    """Convert image bytes to base64 string for embedding."""
    return base64.b64encode(image_bytes).decode()


# --------------- Stage: Setup ---------------

def view_setup():
    st.title("🧠 Memory Spiel")
    st.caption("Jetzt mit anklickbaren Karten!")

    st.sidebar.header("Einstellungen")
    st.session_state.cols = st.sidebar.slider("Spalten", min_value=2, max_value=8, value=st.session_state.cols, step=1)
    st.session_state.size_px = st.sidebar.slider("Kartengröße (px)", min_value=100, max_value=300, value=st.session_state.size_px, step=10)

    st.subheader("1) Rückseiten-Bild hochladen (wird für alle Karten verwendet)")
    back = st.file_uploader("Rückseiten-Bild", type=["png", "jpg", "jpeg", "webp"], key="u_back")
    if back is not None:
        st.session_state.back_img = back.read()
        st.image(st.session_state.back_img, caption="Rückseiten-Bild", width=120)

    st.subheader("2) Vorderseiten-Bilder hochladen (werden manuell gepaart)")
    face_files = st.file_uploader("Vorderseiten-Bilder", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True, key="u_faces")

    if face_files:
        faces = []
        for i, f in enumerate(face_files):
            try:
                content = f.read()
            except Exception:
                continue
            faces.append({"id": i, "name": f.name, "bytes": content})
        st.session_state.faces = faces

        # Preview grid
        st.caption("Vorschau der hochgeladenen Bilder")
        cols = st.columns(min(st.session_state.cols, max(1, len(faces))))
        for idx, face in enumerate(faces):
            with cols[idx % len(cols)]:
                st.image(face["bytes"], caption=face["name"], width=st.session_state.size_px)

    st.markdown("---")
    can_continue = (st.session_state.back_img is not None) and (len(st.session_state.faces) >= 2)
    if not can_continue:
        st.info("Lade 1 Rückseiten-Bild und mindestens 2 Vorderseiten-Bilder hoch, um fortzufahren.")
    if st.button("➡️ Diese Bilder verwenden", disabled=not can_continue):
        # Initialize pairing state
        st.session_state.unpaired_ids = set([f["id"] for f in st.session_state.faces])
        st.session_state.pair_bucket = []
        st.session_state.pairs = []
        st.session_state.stage = "pair"
        st.session_state.revealed = []
        st.session_state.mismatch_pending = False
        st.session_state.deck = []
        _rerun()


# --------------- Stage: Pair ---------------

def view_pair():
    st.title("👫 Paare erstellen")
    st.caption("Wähle zwei Bilder aus, um ein Paar zu erstellen. Du kannst ein Bild mit sich selbst paaren.")

    # Sidebar controls for pairing
    st.sidebar.header("Paar-Verwaltung")
    
    # Add Pair bucket status to sidebar - show both images side by side
    st.sidebar.subheader("Aktuelles Paar")
    face_by_id = _face_lookup()
    
    if len(st.session_state.pair_bucket) == 0:
        st.sidebar.info("Wähle das erste Bild aus")
    elif len(st.session_state.pair_bucket) == 1:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            fid = st.session_state.pair_bucket[0]
            st.image(face_by_id[fid]["bytes"], caption=face_by_id[fid]["name"], width=70)
        with col2:
            st.write("**+**")
            st.write("Wähle zweites Bild")
    elif len(st.session_state.pair_bucket) == 2:
        col1, col2, col3 = st.sidebar.columns([1,1,1])
        with col1:
            fid1 = st.session_state.pair_bucket[0]
            st.image(face_by_id[fid1]["bytes"], caption=face_by_id[fid1]["name"], width=60)
        with col2:
            st.write("**↔**")
        with col3:
            fid2 = st.session_state.pair_bucket[1]
            st.image(face_by_id[fid2]["bytes"], caption=face_by_id[fid2]["name"], width=60)
        
        # Manual commit button
        if st.sidebar.button("✅ Paar erstellen", type="primary"):
            a, b = st.session_state.pair_bucket
            st.session_state.pairs.append([a, b])
            # Remove from unpaired set (self-pair removes once)
            st.session_state.unpaired_ids.discard(a)
            st.session_state.unpaired_ids.discard(b)
            st.session_state.pair_bucket = []
            _rerun()
        
        if st.sidebar.button("🗑️ Auswahl löschen"):
            st.session_state.pair_bucket = []
            _rerun()
    
    st.sidebar.markdown("---")
    
    # Pair management buttons
    if st.sidebar.button("🧹 Alle Paare löschen", disabled=(len(st.session_state.pairs) == 0 and len(st.session_state.pair_bucket) == 0)):
        st.session_state.unpaired_ids = set([f["id"] for f in st.session_state.faces])
        st.session_state.pairs = []
        st.session_state.pair_bucket = []
        _rerun()
        
    can_start = len(st.session_state.pairs) > 0
    if st.sidebar.button("▶️ Spiel starten", disabled=not can_start):
        start_game()
        _rerun()
        
    st.sidebar.markdown("---")
    if st.sidebar.button("⬅️ Zurück zur Einrichtung"):
        st.session_state.stage = "setup"
        _rerun()

    # Unpaired grid with "Add to pair" buttons
    st.subheader("Verfügbare Bilder")
    unpaired = [face_by_id[i] for i in st.session_state.unpaired_ids]
    if not unpaired:
        st.success("Alle Bilder sind gepaart. Du kannst das Spiel starten!")
    else:
        st.write(f"**{len(unpaired)} Bilder** verfügbar zum Paaren")
        
        grid_cols = st.columns(min(st.session_state.cols, max(1, len(unpaired))))
        clicked_to_add = None
        for idx, face in enumerate(unpaired):
            with grid_cols[idx % len(grid_cols)]:
                st.image(face["bytes"], caption=face["name"], width=st.session_state.size_px)
                
                # Check if this image is already in pair bucket
                is_selected = face["id"] in st.session_state.pair_bucket
                button_text = "✓ Ausgewählt" if is_selected else "➕ Auswählen"
                button_disabled = is_selected or len(st.session_state.pair_bucket) >= 2
                
                if st.button(button_text, key=f"add_{face['id']}", disabled=button_disabled, type="primary" if is_selected else "secondary"):
                    if not is_selected:
                        clicked_to_add = face["id"]
                    
        if clicked_to_add is not None:
            st.session_state.pair_bucket.append(clicked_to_add)
            _rerun()

    # Pairs so far
    if st.session_state.pairs:
        st.subheader(f"Erstellte Paare ({len(st.session_state.pairs)})")
        
        # Create a container for better layout
        pairs_container = st.container()
        
        pairs_to_delete = []  # Track which pairs to delete
        
        for i, (a, b) in enumerate(st.session_state.pairs):
            with pairs_container:
                # Create columns for pair display and delete button
                pair_col, delete_col = st.columns([4, 1])
                
                with pair_col:
                    # Display the pair images side by side
                    img_col1, img_col2 = st.columns(2)
                    with img_col1:
                        st.image(face_by_id[a]["bytes"], width=100)
                        st.caption(face_by_id[a]['name'])
                    with img_col2:
                        st.image(face_by_id[b]["bytes"], width=100) 
                        st.caption(face_by_id[b]['name'])
                
                with delete_col:
                    # Add some spacing and center the delete button
                    st.write("")  # Add space
                    st.write("")  # Add space
                    if st.button("🗑️", key=f"delete_pair_{i}", help=f"Paar #{i+1} löschen"):
                        pairs_to_delete.append(i)
                
                st.divider()  # Clean separator between pairs
        
        # Process deletions (in reverse order to maintain indices)
        for pair_index in sorted(pairs_to_delete, reverse=True):
            if pair_index < len(st.session_state.pairs):  # Safety check
                a, b = st.session_state.pairs.pop(pair_index)
                # Add back to unpaired set
                st.session_state.unpaired_ids.add(a)
                st.session_state.unpaired_ids.add(b)
                _rerun()


# --------------- Build & Play ---------------

def start_game():
    '''Build the deck from pairs and enter play stage.'''
    # Build 2 cards per pair with same pair_idx
    deck = []
    pos = 0
    for pair_idx, (a, b) in enumerate(st.session_state.pairs):
        deck.append({"pos": pos, "pair_idx": pair_idx, "face_id": a, "matched": False})
        pos += 1
        deck.append({"pos": pos, "pair_idx": pair_idx, "face_id": b, "matched": False})
        pos += 1
    random.shuffle(deck)
    # Reset play state
    st.session_state.deck = deck
    st.session_state.revealed = []
    st.session_state.mismatch_pending = False
    st.session_state.game_won = False
    st.session_state.stage = "play"


def generate_memory_game_html():
    """Generate complete HTML with embedded JavaScript for zero-reload gameplay."""
    
    size = st.session_state.size_px
    cols_count = st.session_state.cols
    spacing = st.session_state.card_spacing
    container_scale = st.session_state.get("container_scale", 100)
    face_by_id = _face_lookup()
    
    # Convert all images to base64
    back_img_b64 = _image_to_base64(st.session_state.back_img)
    
    # Build card data for JavaScript - properly serialize to JSON
    cards_data = []
    for card in st.session_state.deck:
        face_img_b64 = _image_to_base64(face_by_id[card["face_id"]]["bytes"])
        cards_data.append({
            "pos": card["pos"],
            "pair_idx": card["pair_idx"],
            "face_id": card["face_id"],
            "face_name": face_by_id[card["face_id"]]["name"],
            "face_img": face_img_b64,
            "matched": False
        })
    
    # Properly serialize to JSON
    cards_json = json.dumps(cards_data)
    total_pairs = len(st.session_state.pairs)
    
    # Generate the complete HTML
    html_content = f"""
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Memory Game</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        
        body {{
            margin: 0;
            padding: 10px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f8f9fa;
            height: 100vh;
            overflow: hidden;
            display: flex;
            align-items: flex-start;
            justify-content: center;
        }}
        
        .game-container {{
            max-width: 1200px;
            height: 100vh;
            display: flex;
            flex-direction: column;
            transform: scale({container_scale / 100});
            transform-origin: center top;
            transition: transform 0.3s ease;
        }}
        
        .progress-container {{
            background: white;
            border-radius: 15px;
            padding: 15px 20px;
            margin-bottom: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            flex-shrink: 0;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #45a049);
            width: 0%;
            transition: width 0.5s ease;
        }}
        
        .progress-text {{
            margin-top: 10px;
            color: #666;
            font-size: 14px;
        }}
        
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat({cols_count}, 1fr);
            gap: {spacing}px;
            justify-items: center;
            align-items: center;
            padding: 20px;
            background: white;
            border-radius: 15px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            flex: 1;
            overflow: hidden;
            max-height: calc(100vh - 120px);
        }}
        
        .card {{
            width: {size}px;
            height: {size}px;
            position: relative;
            cursor: pointer;
            border-radius: 12px;
            transition: transform 0.2s ease;
            perspective: 1000px;
        }}
        
        .card:hover:not(.matched):not(.flipped) {{
            transform: scale(1.05);
        }}
        
        .card-inner {{
            position: relative;
            width: 100%;
            height: 100%;
            transition: transform 0.6s;
            transform-style: preserve-3d;
        }}
        
        .card.flipped .card-inner {{
            transform: rotateY(180deg);
        }}
        
        .card.matched .card-inner {{
            transform: rotateY(180deg);
        }}
        
        .card-face {{
            position: absolute;
            width: 100%;
            height: 100%;
            backface-visibility: hidden;
            border-radius: 12px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            overflow: hidden;
            border: 3px solid #ddd;
        }}
        
        .card-back {{
            background: #ddd;
        }}
        
        .card-front {{
            transform: rotateY(180deg);
        }}
        
        .card-face img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
        }}
        
        .card.matched {{
            pointer-events: none;
        }}
        
        .card.matched .card-face {{
            border-color: #4CAF50;
        }}
        
        .card.matched::after {{
            content: '✓';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #4CAF50;
            font-size: 32px;
            font-weight: bold;
            background: rgba(255,255,255,0.9);
            width: 50px;
            height: 50px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10;
            animation: matchPulse 1s ease-in-out;
        }}
        
        @keyframes matchPulse {{
            0% {{ transform: translate(-50%, -50%) scale(0); }}
            50% {{ transform: translate(-50%, -50%) scale(1.2); }}
            100% {{ transform: translate(-50%, -50%) scale(1); }}
        }}
        
        .win-message {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            text-align: center;
            z-index: 1000;
            display: none;
        }}
        
        .win-message.show {{
            display: block;
            animation: winAppear 0.5s ease-out;
        }}
        
        @keyframes winAppear {{
            from {{ transform: translate(-50%, -50%) scale(0.5); opacity: 0; }}
            to {{ transform: translate(-50%, -50%) scale(1); opacity: 1; }}
        }}
        
        .overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 999;
            display: none;
        }}
        
        .overlay.show {{
            display: block;
        }}
        
        .win-button {{
            background: #4CAF50;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 16px;
            cursor: pointer;
            margin: 10px;
            transition: background 0.3s;
        }}
        
        .win-button:hover {{
            background: #45a049;
        }}
    </style>
</head>
<body>
    <div class="game-container">
        <div class="progress-container">
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            <div class="progress-text" id="progressText">Fortschritt: 0/{total_pairs} Paare gefunden</div>
        </div>
        
        <div class="cards-grid" id="cardsGrid">
            <!-- Cards will be generated by JavaScript -->
        </div>
    </div>
    
    <div class="overlay" id="overlay"></div>
    <div class="win-message" id="winMessage">
        <h2>🎉 Alle Paare gefunden!</h2>
        <p>Herzlichen Glückwunsch zum Gewinn!</p>
        <button class="win-button" onclick="location.reload()">🔄 Nochmal spielen</button>
    </div>

    <script>
        console.log('Memory game script starting...');
        
        // Game state
        const CARDS_DATA = {cards_json};
        const BACK_IMAGE = "data:image/png;base64,{back_img_b64}";
        const TOTAL_PAIRS = {total_pairs};
        
        console.log('Cards data:', CARDS_DATA);
        console.log('Total pairs:', TOTAL_PAIRS);
        
        let gameState = {{
            revealed: [],
            matchedPairs: 0,
            isProcessing: false
        }};
        
        // Initialize game
        function initGame() {{
            console.log('Initializing game...');
            
            const grid = document.getElementById('cardsGrid');
            if (!grid) {{
                console.error('Grid container not found!');
                return;
            }}
            
            grid.innerHTML = '';
            
            CARDS_DATA.forEach((cardData, index) => {{
                console.log(`Creating card ${{index}}:`, cardData);
                const card = createCard(cardData);
                grid.appendChild(card);
            }});
            
            updateProgress();
        }}
        
        function createCard(cardData) {{
            const card = document.createElement('div');
            card.className = 'card';
            card.dataset.pos = cardData.pos;
            card.dataset.pairIdx = cardData.pair_idx;
            
            const backImage = `<img src="${{BACK_IMAGE}}" alt="Card back" onerror="console.error('Failed to load back image')" />`;
            const frontImage = `<img src="data:image/png;base64,${{cardData.face_img}}" alt="${{cardData.face_name}}" onerror="console.error('Failed to load front image for ${{cardData.face_name}}')" />`;
            
            card.innerHTML = `
                <div class="card-inner">
                    <div class="card-face card-back">
                        ${{backImage}}
                    </div>
                    <div class="card-face card-front">
                        ${{frontImage}}
                    </div>
                </div>
            `;
            
            card.addEventListener('click', () => handleCardClick(card));
            return card;
        }}
        
        function handleCardClick(card) {{
            console.log('Card clicked:', card.dataset.pos);
            
            if (gameState.isProcessing) {{
                console.log('Game is processing, ignoring click');
                return;
            }}
            if (card.classList.contains('flipped') || card.classList.contains('matched')) {{
                console.log('Card already flipped or matched, ignoring click');
                return;
            }}
            if (gameState.revealed.length >= 2) {{
                console.log('Already 2 cards revealed, ignoring click');
                return;
            }}
            
            // Flip card
            card.classList.add('flipped');
            gameState.revealed.push(card);
            console.log('Revealed cards:', gameState.revealed.length);
            
            if (gameState.revealed.length === 2) {{
                gameState.isProcessing = true;
                setTimeout(checkMatch, 800);
            }}
        }}
        
        function checkMatch() {{
            const [card1, card2] = gameState.revealed;
            const pair1 = card1.dataset.pairIdx;
            const pair2 = card2.dataset.pairIdx;
            
            console.log(`Checking match: ${{pair1}} vs ${{pair2}}`);
            
            if (pair1 === pair2) {{
                // Match!
                console.log('Match found!');
                card1.classList.add('matched');
                card2.classList.add('matched');
                gameState.matchedPairs++;
                updateProgress();
                
                if (gameState.matchedPairs === TOTAL_PAIRS) {{
                    setTimeout(showWin, 500);
                }}
            }} else {{
                // No match - flip back
                console.log('No match, flipping back');
                setTimeout(() => {{
                    card1.classList.remove('flipped');
                    card2.classList.remove('flipped');
                }}, 1000);
            }}
            
            gameState.revealed = [];
            gameState.isProcessing = false;
        }}
        
        function updateProgress() {{
            const progress = (gameState.matchedPairs / TOTAL_PAIRS) * 100;
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            
            if (progressFill) {{
                progressFill.style.width = progress + '%';
            }}
            if (progressText) {{
                progressText.textContent = `Fortschritt: ${{gameState.matchedPairs}}/${{TOTAL_PAIRS}} Paare gefunden`;
            }}
        }}
        
        function showWin() {{
            console.log('Game won!');
            document.getElementById('overlay').classList.add('show');
            document.getElementById('winMessage').classList.add('show');
            
            // Trigger confetti effect
            createConfetti();
        }}
        
        function createConfetti() {{
            for (let i = 0; i < 50; i++) {{
                setTimeout(() => {{
                    const confetti = document.createElement('div');
                    confetti.style.cssText = `
                        position: fixed;
                        width: 10px;
                        height: 10px;
                        background: hsl(${{Math.random() * 360}}deg, 70%, 60%);
                        top: -10px;
                        left: ${{Math.random() * 100}}%;
                        animation: fall ${{2 + Math.random() * 3}}s linear forwards;
                        z-index: 1001;
                        border-radius: 50%;
                    `;
                    document.body.appendChild(confetti);
                    
                    setTimeout(() => confetti.remove(), 5000);
                }}, i * 100);
            }}
        }}
        
        // Add CSS for confetti animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes fall {{
                to {{
                    transform: translateY(100vh) rotate(360deg);
                }}
            }}
        `;
        document.head.appendChild(style);
        
        // Start the game when DOM is ready
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', initGame);
        }} else {{
            initGame();
        }}
        
        console.log('Memory game script loaded successfully');
    </script>
</body>
</html>
    """
    
    return html_content


def view_play():
    # Sidebar controls for gameplay
    st.sidebar.header("Spiel-Einstellungen")
    st.session_state.size_px = st.sidebar.slider("Kartengröße (px)", min_value=80, max_value=400, value=st.session_state.size_px, step=10)
    st.session_state.card_spacing = st.sidebar.slider("Kartenabstand (px)", min_value=2, max_value=30, value=st.session_state.card_spacing, step=2)
    st.session_state.cols = st.sidebar.slider("Spalten", min_value=2, max_value=8, value=st.session_state.cols, step=1)
    
    # Add container scale control
    if "container_scale" not in st.session_state:
        st.session_state.container_scale = 100
    st.session_state.container_scale = st.sidebar.slider("Container-Größe (%)", min_value=50, max_value=150, value=st.session_state.container_scale, step=5)

    st.sidebar.markdown("---")
    st.sidebar.header("Spiel-Aktionen")
    
    # Game action buttons in sidebar
    if st.sidebar.button("🔄 Neue Mischung"):
        start_game()
        _rerun()
        
    if st.sidebar.button("✏️ Paare ändern"):
        st.session_state.stage = "pair"
        st.session_state.revealed = []
        st.session_state.mismatch_pending = False
        _rerun()
        
    if st.sidebar.button("🧰 Zurück zur Einrichtung"):
        st.session_state.stage = "setup"
        _rerun()

    # Game stats in sidebar
    st.sidebar.markdown("---")
    st.sidebar.header("Spiel-Info")
    st.sidebar.metric("Karten gesamt", len(st.session_state.deck))
    st.sidebar.metric("Paare zu finden", len(st.session_state.pairs))

    # Generate and render the pure HTML game - full page
    game_html = generate_memory_game_html()
    # Calculate height to use full available space
    scaled_height = int(800 * (st.session_state.get("container_scale", 100) / 100))
    components.html(game_html, height=scaled_height, scrolling=False)


# --------------- Stage: Win ---------------

def view_win():
    st.title("✅ Alle Paare gefunden!")
    st.balloons()
    
    # Show final score/stats (German translation)
    total_cards = len(st.session_state.deck)
    total_pairs = len(st.session_state.pairs)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Gesamte Karten", total_cards)
    with col2:
        st.metric("Gefundene Paare", total_pairs)
    with col3:
        st.metric("Erfolgsrate", "100%")
    
    st.markdown("---")
    left, right = st.columns(2)
    with left:
        if st.button("🔄 Nochmal spielen (neue Mischung)"):
            start_game()
            _rerun()
    with right:
        if st.button("✏️ Paare ändern"):
            st.session_state.stage = "pair"
            _rerun()

    st.markdown("---")
    if st.button("🧰 Neu starten (neue Bilder)"):
        for key in ["stage","back_img","faces","unpaired_ids","pair_bucket","pairs","deck","revealed","mismatch_pending"]:
            if key in st.session_state:
                del st.session_state[key]
        _init_state()
        _rerun()


# --------------- App Entrypoint ---------------

def main():
    st.set_page_config(
        page_title="Memory Spiel",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    _init_state()
    stage = st.session_state.stage
    if stage == "setup":
        view_setup()
    elif stage == "pair":
        view_pair()
    elif stage == "play":
        view_play()
    elif stage == "win":
        view_win()
    else:
        st.session_state.stage = "setup"
        view_setup()


if __name__ == "__main__":
    main()