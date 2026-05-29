(function () {
  const SHOP_ITEMS = [
    {
      id: "encounter_reroll",
      name: "Encounter Reroll",
      cost: 1,
      description: "REROLL YOUR FIRST ENCOUNTER ON THE CURRENT ROUTE. YOU CANNOT USE MORE THAN ONE ENCOUNTER REROLL ON EACH ROUTE. THE REROLL MUST BE THE SAME ENCOUNTER TYPE AS YOUR FIRST ENCOUNTER.",
      category: "Encounters",
    },
    {
      id: "encounter_reroll_2",
      name: "Encounter Reroll 2",
      cost: 0,
      description: "REROLL YOUR FIRST ENCOUNTER ON THE CURRENT ROUTE. YOU CANNOT USE MORE THAN ONE ENCOUNTER REROLL ON EACH ROUTE. THE REROLL MUST BE THE SAME ENCOUNTER TYPE AS YOUR FIRST ENCOUNTER.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "safari_hunt",
      name: "Safari Hunt",
      cost: 2,
      description: "GAIN AN ADDITIONAL SAFARI ZONE RUN & ENCOUNTER. IF THE ENCOUNTERED POKEMON RUNS, ROLL ANOTHER ENCOUNTER OF THE SAME ENCOUNTER TYPE, CONTINUE DOING SO UNTIL YOU SUCCESSFULLY CATCH A POKEMON IN THIS WAY. YOU MAY NOT THROW ROCKS DURING THESE ENCOUNTERS.",
      category: "Encounters",
    },
    {
      id: "safari_hunt_2",
      name: "Safari Hunt 2",
      cost: 0,
      description: "GAIN AN ADDITIONAL SAFARI ZONE RUN & ENCOUNTER. IF THE ENCOUNTERED POKEMON RUNS, ROLL ANOTHER ENCOUNTER OF THE SAME ENCOUNTER TYPE, CONTINUE DOING SO UNTIL YOU SUCCESSFULLY CATCH A POKEMON IN THIS WAY. YOU MAY NOT THROW ROCKS DURING THESE ENCOUNTERS.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "target_hunt",
      name: "Targeted Hunt",
      cost: 5,
      description: "REROLL ALL ENCOUNTERS ON A ROUTE OF YOUR CHOICE UNTIL YOUR FIRST ENCOUNTER OF A SPECIFIED SPECIES. THE TARGET SPECIES MUST BE DECLARED IMMEDIATELY AFTER REDEMPTION AND CANNOT BE CHANGED.",
      category: "Encounters",
    },
    {
      id: "spelunker",
      name: "Spelunker",
      cost: 2,
      description: "GAIN AN ENCOUNTER WITH THE FIRST POKEMON YOU ENCOUNTER ON ANY FLOOR OF ANY CAVE. YOU MAY NOT USE DEXNAV FOR THE ENCOUNTER.",
      category: "Encounters",
    },
    {
      id: "cryptid_hunter",
      name: "Cryptid Hunter",
      cost: 2,
      description: "CHOOSE ANY ROUTE: YOU HAVE TEN CHANCES TO ENCOUNTER THE RAREST SPAWN THERE, IF YOU DO YOU MAY CATCH IT. IF THE RAREST SPAWN IS A TIE, THEN ANY OF THOSE SPAWNS COUNT. THE CHOSEN ROUTE MUST HAVE MORE THAN ONE POSSIBLE SPAWN. YOU MAY NOT USE DEXNAV FOR YOUR ENCOUNTER.",
      category: "Encounters",
    },
    {
      id: "fishing_boon",
      name: "Fishing Boon",
      cost: 2,
      description: "GAIN AN ADDITIONAL FISHING ENCOUNTER ON A ROUTE YOU DID NOT FISH ON PREVIOUSLY.",
      category: "Encounters",
    },
    {
      id: "surf_s_up",
      name: "Surf's Up",
      cost: 2,
      description: "GAIN AN ADDITIONAL SURFING ENCOUNTER ON A ROUTE YOU DID NOT PERFORM A SURFING ENCOUNTER ON PREVIOUSLY. YOU MAY NOT USE DEXNAV FOR THE ENCOUNTER. IF YOU FAIL THE ENCOUNTER, YOU DO NOT GET ANOTHER CHANCE.",
      category: "Encounters",
    },
    {
      id: "surf_s_up_2",
      name: "Surf's Up 2",
      cost: 0,
      description: "GAIN AN ADDITIONAL SURFING ENCOUNTER ON A ROUTE YOU DID NOT PERFORM A SURFING ENCOUNTER ON PREVIOUSLY. YOU MAY NOT USE DEXNAV FOR THE ENCOUNTER. IF YOU FAIL THE ENCOUNTER, YOU DO NOT GET ANOTHER CHANCE.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "fishing_boon_2",
      name: "Fishing Boon 2",
      cost: 0,
      description: "GAIN AN ADDITIONAL FISHING ENCOUNTER ON A ROUTE YOU DID NOT FISH ON PREVIOUSLY.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "raid_roll",
      name: "Raid Roll",
      cost: 3,
      description: "GAIN AN ENCOUNTER AT A RAID DEN OF YOUR CHOICE WITH THE ABILITY TO CAPTURE AND USE THE ENCOUNTERED RAID POKEMON.",
      category: "Encounters",
    },
    {
      id: "raid_roll_2",
      name: "Raid Roll 2",
      cost: 0,
      description: "GAIN AN ENCOUNTER AT A RAID DEN OF YOUR CHOICE WITH THE ABILITY TO CAPTURE AND USE THE ENCOUNTERED RAID POKEMON.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "boss_reset",
      name: "Boss Reset",
      cost: 3,
      description: "WHILE AT LEAST ONE MEMBER OF YOUR PARTY REMAINS, RELOAD A SAVE FILE FROM BEFORE THE CURRENT BOSS BATTLE. YOU CANNOT REDEEM THIS BOON IF YOU HAVE ALREADY LOST THE BATTLE.",
      category: "Lifeline",
    },
    {
      id: "boss_reset_2",
      name: "Boss Reset 2",
      cost: 0,
      description: "WHILE AT LEAST ONE MEMBER OF YOUR PARTY REMAINS, RELOAD A SAVE FILE FROM BEFORE THE CURRENT BOSS BATTLE. YOU CANNOT REDEEM THIS BOON IF YOU HAVE ALREADY LOST THE BATTLE.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "next_of_kin",
      name: "Next Of Kin",
      cost: 2,
      description: "GO BACK TO THE ROUTE YOU CAUGHT A FAINTED POKEMON YOU OWN ON AND GAIN AN ENCOUNTER WITH THE FIRST POKEMON OF THE SAME SPECIES OR SAME EVOLUTION FAMILY THAT YOU ENCOUNTER THERE. THE ROUTE MUST BE THE ONE SPECIFIED IN THE FAINTED POKEMON'S SUMMARY. REGIONAL FORMS ARE CONSIDERED TO BE PART OF THE POKEMON'S EVOLUTION FAMILY.",
      category: "Lifeline",
    },
    {
      id: "revive",
      name: "Revive",
      cost: 3,
      description: "REVIVE ONE OF YOUR FAINTED POKEMON. THIS BOON CAN ONLY BE UTILIZED OUTSIDE OF BATTLE.",
      category: "Lifeline",
    },
    {
      id: "revive_2",
      name: "Revive 2",
      cost: 0,
      description: "REVIVE ONE OF YOUR FAINTED POKEMON. THIS BOON CAN ONLY BE UTILIZED OUTSIDE OF BATTLE.",
      category: "Awards",
      purchasable: false,
    },
      {
      id: "bird_watcher",
      name: "Bird Watcher",
      cost: 0,
      description: "GAIN A FREE ENCOUNTER WITH THE FIRST FLYING-TYPE POKEMON YOU ENCOUNTER ON A ROUTE OF YOUR CHOICE. YOU MAY NOT USE DEXNAV TO CHOOSE YOUR ENCOUNTER. IF YOU FAIL THE ENCOUNTER, YOU DO NOT GET ANOTHER CHANCE.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "bug_catcher",
      name: "Bug Catcher",
      cost: 0,
      description: "GAIN A FREE ENCOUNTER WITH THE FIRST BUG-TYPE POKEMON YOU ENCOUNTER ON A ROUTE OF YOUR CHOICE. YOU MAY NOT USE DEXNAV TO CHOOSE YOUR ENCOUNTER. IF YOU FAIL THE ENCOUNTER, YOU DO NOT GET ANOTHER CHANCE.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "ex_boyfriend",
      name: "Ex-Boyfriend",
      cost: 0,
      description: "RELEASE A MALE POKEMON YOU OWN, THEN GAIN AN ENCOUNTER WITH THE FIRST MALE POKEMON YOU ENCOUNTER ON A ROUTE OF YOUR CHOICE. YOU MAY NOT USE DEXNAV TO CHOOSE YOUR ENCOUNTER. IF YOU FAIL THE ENCOUNTER, YOU DO NOT GET ANOTHER CHANCE. YOU MAY NOT REDEEM THIS BOON IF YOU DO NOT OWN A MALE POKEMON. YOU CANNOT RELEASE A DEAD POKEMON. YOU MUST FOLLOW THE INSTRUCTIONS OF THIS BOON IN ORDER.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "next_of_kin_2",
      name: "Next Of Kin 2",
      cost: 0,
      description: "GO BACK TO THE ROUTE YOU CAUGHT A FAINTED POKEMON YOU OWN ON AND GAIN AN ENCOUNTER WITH THE FIRST POKEMON OF THE SAME SPECIES OR SAME EVOLUTION FAMILY THAT YOU ENCOUNTER THERE. THE ROUTE MUST BE THE ONE SPECIFIED IN THE FAINTED POKEMON'S SUMMARY. REGIONAL FORMS ARE CONSIDERED TO BE PART OF THE POKEMON'S EVOLUTION FAMILY.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "hatch_of_the_day",
      name: "Hatch Of The Day",
      cost: 0,
      description: "YOU MAY HATCH ANY EGG OBTAINED FROM AN NPC. THIS DOES NOT COUNT AS YOUR ENCOUNTER IN THE TOWN OR ROUTE WHERE YOU OBTAINED THE EGG.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "cash_out",
      name: "Cash Out",
      cost: 0,
      description: "YOU MAY RELEASE ANY NUMBER OF LIVING POKEMON THAT YOU OWN IN STORAGE. GAIN 1 POINT FOR EACH POKEMON RELEASED THIS WAY. YOU MUST RELEASE ALL OF THOSE POKEMON AT ONCE IMMEDIATELY AFTER REDEMPTION AND CANNOT MAKE PURCHASES IN-BETWEEN.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "foresight",
      name: "Foresight",
      cost: 0,
      description: "DECLARE YOUR NEXT BOSS BATTLE. THE TARGET CAN BE ANY TRAINER THAT AWARDS POINTS UPON DEFEAT. AFTER DECLARATION, YOU MAY NOT BATTLE OTHER BOSS TRAINERS UNTIL THE DECLARED TRAINER IS DEFEATED. GAIN AN ENCOUNTER WITH ANY POKEMON WHOSE PRIMARY TYPE IS SUPER-EFFECTIVE AGAINST THE FIRST POKEMON IN THAT TRAINER'S PARTY.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "harvest_season",
      name: "Harvest Season",
      cost: 0,
      description: "YOU MAY RELEASE ANY NUMBER OF GRASS-TYPE POKEMON THAT YOU OWN, EITHER LIVING AND/OR DEAD. GAIN 3 POINTS FOR EACH LIVING POKEMON RELEASED THIS WAY AND 1 POINT FOR EACH DEAD POKEMON RELEASED THIS WAY. YOU MUST RELEASE ALL OF THESE POKEMON AT ONCE IMMEDIATELY AFTER REDEMPTION AND CANNOT MAKE PURCHASES OR OTHER REDEMPTIONS IN-BETWEEN.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "bunshin_technique",
      name: "Bunshin Technique",
      cost: 0,
      description: "GAIN AN ENCOUNTER WITH ANY LIVING POKEMON THAT YOU ALREADY OWN ON ANY ROUTE THAT IT OR ITS EVOLUTION FAMILY APPEAR ON (EXCLUDES DIFFERING FORMS). IT MUST REMAIN IN THE SAME EVOLUTIONARY STAGE AS THE CHOSEN POKEMON FOR AS LONG AS YOU OWN BOTH, EVEN IF ONE OR BOTH DIES.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "gift_pokemon_2",
      name: "Gift Pokemon 2",
      cost: 0,
      description: "CLAIM A GIFT POKEMON OF YOUR CHOICE FROM AN NPC OR ONE THAT IS OTHERWISE AWARDED WITHOUT ACTUALLY ENCOUNTERING IT.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "high_roller_2",
      name: "High Roller 2",
      cost: 0,
      description: "YOU MAY PURCHASE AN ADDITIONAL POKEMON AT THE CELADON CITY GAME CORNER.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "all_in",
      name: "All In",
      cost: 0,
      description: "BET X POINTS. CHOOSE SOMEONE ELSE TO FLIP A COIN FOR YOU; CALL IT. IF YOU CALLED IT RIGHT, GAIN 2X POINTS, OTHERWISE LOSE X POINTS. IF YOU GO BELOW 0 POINTS IN THIS WAY, YOU LOSE THE NUZLOCKE. YOU MUST MAKE YOUR CALL BEFORE THE COIN FLIP ENDS AND CANNOT CHANGE YOUR DECISION. THE COIN CANNOT BE FLIPPED MORE THAN ONCE. X CANNOT BE MORE POINTS THAN YOU CURRENTLY POSSESS PRIOR TO REDEMPTION.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "black_market_trading",
      name: "Black Market Trading",
      cost: 0,
      description: "CHOOSE ANY ONE LIVING POKEMON OWNED BY ANOTHER PLAYER: THAT PLAYER GAINS 5 POINTS AND THEN MUST IMMEDIATELY RELEASE IT. THEN YOU GAIN AN ENCOUNTER WITH THAT POKEMON OR ANY MEMBER OF ITS EVOLUTIONARY FAMILY ON ANY ROUTE ON WHICH IT APPEARS. THE SELECTED PLAYER DOES NOT HAVE A CHOICE IN THIS DECISION AND CANNOT REFUSE.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "soft_reset_2",
      name: "Soft Reset 2",
      cost: 0,
      description: "CONTINUE PLAYING AFTER ALL POKEMON IN YOUR PARTY HAVE BEEN KNOCKED OUT AND REVIVE ALL OF YOUR PARTY POKEMON.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "dragon_tamer",
      name: "Dragon Tamer",
      cost: 0,
      description: "YOU GAIN AN ENCOUNTER WITH THE FIRST DRAGON-TYPE POKEMON YOU ENCOUNTER ON A ROUTE OF YOUR CHOICE. YOU MAY NOT USE DEXNAV FOR THE ENCOUNTER.",
      category: "Awards",
      purchasable: false,
    },
    {
      id: "soft_reset",
      name: "Soft Reset",
      cost: 10,
      description: "CONTINUE PLAYING AFTER ALL POKEMON IN YOUR PARTY HAVE BEEN KNOCKED OUT AND REVIVE ALL OF YOUR PARTY POKEMON.",
      category: "Lifeline",
    },
    {
      id: "event_encounter",
      name: "Event Encounter",
      cost: 2,
      description: "CLAIM AN ENCOUNTER WITH AN EVENT POKEMON EVEN IF YOU'VE ALREADY FULFILLED YOUR ENCOUNTER ON THE ROUTE IT EXISTS ON. YOU CANNOT REDEEM MORE THAN ONE EVENT ENCOUNTER ON A ROUTE.",
      category: "Events",
    },
    {
      id: "gift_pokemon",
      name: "Gift Pokemon",
      cost: 2,
      description: "CLAIM A GIFT POKEMON OF YOUR CHOICE FROM AN NPC OR ONE THAT IS OTHERWISE AWARDED WITHOUT ACTUALLY ENCOUNTERING IT.",
      category: "Events",
    },
    {
      id: "high_roller",
      name: "High Roller",
      cost: 3,
      description: "YOU MAY PURCHASE AN ADDITIONAL POKEMON AT THE CELADON CITY GAME CORNER.",
      category: "Events",
    },
    {
      id: "in_game_trade",
      name: "In-Game Trade",
      cost: 3,
      description: "COMPLETE A TRADE WITH AN NPC. YOU GAIN A FREE TARGETED HUNT FOR THE FIRST MEMBER OF THE SPECIES REQUIRED FOR THE TRADE THAT YOU ENCOUNTER ON A ROUTE OF YOUR CHOOSING.",
      category: "Events",
    },
    {
      id: "pokemon_breeder",
      name: "Pokemon Breeder",
      cost: 3,
      description: "YOU MAY BREED FOR AN EGG AT THE DAYCARE. YOU MAY CATCH ONE OF THE NECESSARY PARENTS, BUT MUST RELEASE IT AFTER BREEDING IS COMPLETED. YOU MAY ONLY HATCH AND USE THE FIRST EGG OBTAINED IN THIS WAY.",
      category: "Events",
    },
  ];
  const SHOP_ITEM_MAP = new Map(SHOP_ITEMS.map((item) => [String(item.id || ""), item]));

  const STOCK_LIMITS = {
    boss_reset: 20,
    encounter_reroll: 20,
    cryptid_hunter: 5,
    event_encounter: 3,
    fishing_boon: 3,
    gift_pokemon: 3,
    high_roller: 3,
    in_game_trade: 3,
    next_of_kin: 3,
    pokemon_breeder: 1,
    raid_roll: 1,
    revive: 20,
    safari_hunt: 1,
    spelunker: 3,
    surf_s_up: 3,
    soft_reset: 20,
    target_hunt: 10,
  };

  const CATEGORY_ORDER = ["Encounters", "Lifeline", "Events"];
  const REWARD_IMAGE_BASE_PATH = "./points_shop_assets";
  const REWARD_IMAGE_FILE_HINTS = {
    encounter_reroll: "Encounter Reroll.png",
    encounter_reroll_2: "Encounter Reroll 2.png",
    safari_hunt: "Safari Hunt.png",
    safari_hunt_2: "Safari Hunt 2.png",
    target_hunt: "Target Hunt.png",
    spelunker: "Spelunker.png",
    cryptid_hunter: "Cryptid Hunter.png",
    fishing_boon: "Fishing Boon.png",
    fishing_boon_2: "Fishing Boon 2.png",
    surf_s_up: "Surf's Up.png",
    surf_s_up_2: "Surf's Up 2.png",
    raid_roll: "Raid Roll.png",
    raid_roll_2: "Raid Roll 2.png",
    boss_reset: "Boss Reset.png",
    boss_reset_2: "Boss Reset 2.png",
    ex_boyfriend: "Ex-Boyfriend.png",
    next_of_kin: "Next Of Kin.png",
    high_roller_2: "High Roller 2.png",
    revive: "Revive.png",
    revive_2: "Revive 2.png",
    soft_reset: "Soft Reset.png",
    soft_reset_2: "Soft Reset 2.png",
    event_encounter: "Event Encounter.png",
    gift_pokemon: "Gift Pokemon.png",
    gift_pokemon_2: "Gift Pokemon 2.png",
    high_roller: "High Roller.png",
    in_game_trade: "In-Game Trade.png",
    pokemon_breeder: "Pokemon Breeder.png",
    hatch_of_the_day: "Hatch Of The Day.png",
    next_of_kin_2: "Next Of Kin 2.png",
    bird_watcher: "Bird Watcher.png",
    bug_catcher: "Bug Catcher.png",
    cash_out: "Cash Out.png",
    foresight: "Foresight.png",
    harvest_season: "Harvest Season.png",
    bunshin_technique: "Bunshin Technique.png",
    all_in: "All In.png",
    black_market_trading: "Black Market Trading.png",
    dragon_tamer: "Dragon Tamer.png",
  };

  function nowIso(ts) {
    if (!Number.isFinite(ts)) {
      return "";
    }
    try {
      return new Date(ts).toLocaleString();
    } catch (_error) {
      return "";
    }
  }

  function defaultState() {
    return {
      current_points: 0,
      inventory: [],
      unseen_inventory_reward_ids: [],
      unseen_inventory_reward_count: 0,
      transactions: [],
      awarded_trainers: [],
      redeemed_codes: {},
      unlocked_awards: [],
      stock_remaining: {},
      version: 1,
    };
  }

  class PointsShopUI {
    constructor(options) {
      this.root = options.root;
      this.badgeButton = options.badgeButton;
      this.badgeValue = options.badgeValue;
      this.onCommand = options.onCommand;
      this.onUiCommand = options.onUiCommand;
      this.log = options.log || (() => {});

      this.state = defaultState();
      this.previewPointsText = null;
      this.modalOpen = false;
      this.activeTab = "shop";
      this.pendingConfirmItem = null;
      this.lastFocused = null;
      this._seenTxnIds = new Set();
      this._toastedTxnIds = new Set();
      this._stateInitialized = false;
      this.overlayUi = {
        points_shop_open: false,
        points_shop_last_changed_by: null,
        points_shop_changed_at: 0,
      };
      this._purchaseFlashTimer = null;
      this._inventoryPulseTimer = null;
      this._transparentImageCache = new Map();
      this._imageLoadFailures = new Set();
      this._toastQueue = [];
      this._toastActive = false;
      this._pendingTrainerToasts = new Map();
      this._inventoryAckInFlight = false;
      this._badgeClickTimer = null;
      this.pointsEditOpen = false;
      this.redeemModalOpen = false;
      this.redeemInFlight = false;
      this.purchaseLockedDuringBattle = false;
      this._lastPurchaseLockToastAt = 0;
      this._suppressViewSync = false;
      this._viewSyncTimer = null;

      this._buildDom();
      this._bindEvents();
      this._render();
    }

    _buildDom() {
      const container = document.createElement("div");
      container.className = "points-shop-layer";
      container.innerHTML = `
        <div class="points-shop-backdrop" data-close="1"></div>
        <section class="points-shop-modal" role="dialog" aria-modal="true" aria-labelledby="pointsShopTitle" tabindex="-1">
          <header class="points-shop-header">
            <div class="points-shop-heading-wrap">
              <h2 id="pointsShopTitle">Points Shop</h2>
              <nav class="points-shop-tabs" aria-label="Points shop sections">
                <button type="button" class="points-shop-tab is-active" data-tab="shop">Points Shop</button>
                <button type="button" class="points-shop-tab" data-tab="inventory">Inventory</button>
                <button type="button" class="points-shop-tab" data-tab="log">Log</button>
              </nav>
              <div class="points-shop-header-points" aria-live="polite">
                <div class="points-shop-header-points-label">Current Points</div>
                <div class="points-shop-header-points-value" id="pointsShopBalance">0</div>
              </div>
            </div>
            <div class="points-shop-header-actions">
              <button type="button" id="pointsShopRedeemOpen" aria-label="Redeem Code">Redeem</button>
              <button
                type="button"
                class="points-shop-undo points-shop-undo-icon"
                id="pointsShopUndo"
                title="Undo Last Transaction"
                aria-label="Undo Last Transaction"
              >
                ↶
              </button>
              <button type="button" class="points-shop-close" aria-label="Close points shop">Close</button>
            </div>
          </header>
          <div class="points-shop-content">
            <section class="points-shop-panel is-active" data-panel="shop">
              <section class="points-shop-rewards-wrap">
                <h3>Rewards</h3>
                <div class="points-shop-rewards" id="pointsShopRewards"></div>
              </section>
            </section>

            <section class="points-shop-panel" data-panel="inventory">
              <h3>Inventory</h3>
              <div class="points-shop-inventory" id="pointsShopInventory"></div>
            </section>

            <section class="points-shop-panel" data-panel="log">
              <h3>Transaction History</h3>
              <div class="points-shop-history" id="pointsShopHistory"></div>
            </section>
          </div>
        </section>
        <div class="points-edit-overlay" id="pointsEditOverlay" hidden>
          <section class="points-edit-modal" role="dialog" aria-modal="true" aria-labelledby="pointsEditTitle">
            <h3 id="pointsEditTitle">Edit Points</h3>
            <label for="pointsEditInput">Total Points</label>
            <input id="pointsEditInput" type="number" min="0" step="1" inputmode="numeric" />
            <p class="points-edit-status" id="pointsEditStatus" aria-live="polite"></p>
            <div class="points-edit-actions">
              <button type="button" id="pointsEditSave">Save</button>
              <button type="button" id="pointsEditExit">Exit</button>
            </div>
          </section>
        </div>
        <div class="points-edit-overlay" id="pointsRedeemOverlay" hidden>
          <section class="points-edit-modal" role="dialog" aria-modal="true" aria-labelledby="pointsRedeemTitle">
            <h3 id="pointsRedeemTitle">Redeem Code</h3>
            <label for="pointsRedeemInput">Redemption Code</label>
            <input id="pointsRedeemInput" type="text" autocomplete="off" spellcheck="false" />
            <p class="points-edit-status" id="pointsRedeemStatus" aria-live="polite"></p>
            <div class="points-edit-actions">
              <button type="button" id="pointsRedeemSubmit">Redeem</button>
              <button type="button" id="pointsRedeemCancel">Cancel</button>
            </div>
          </section>
        </div>
        <div class="points-shop-confirm-overlay" id="pointsShopConfirm"></div>
      `;

      this.root.appendChild(container);
      this.layer = container;
      this.backdrop = container.querySelector(".points-shop-backdrop");
      this.modal = container.querySelector(".points-shop-modal");
      this.closeButton = container.querySelector(".points-shop-close");
      this.tabButtons = Array.from(container.querySelectorAll(".points-shop-tab"));
      this.tabPanels = Array.from(container.querySelectorAll(".points-shop-panel"));
      this.inventoryTabButton = this.tabButtons.find((button) => String(button.dataset.tab || "") === "inventory") || null;
      this.balanceEl = container.querySelector("#pointsShopBalance");
      this.inventoryEl = container.querySelector("#pointsShopInventory");
      this.rewardsEl = container.querySelector("#pointsShopRewards");
      this.historyEl = container.querySelector("#pointsShopHistory");
      this.contentEl = container.querySelector(".points-shop-content");
      this.redeemOpenButton = container.querySelector("#pointsShopRedeemOpen");
      this.undoButton = container.querySelector("#pointsShopUndo");
      this.confirmEl = container.querySelector("#pointsShopConfirm");
      this.pointsEditOverlay = container.querySelector("#pointsEditOverlay");
      this.pointsEditInput = container.querySelector("#pointsEditInput");
      this.pointsEditStatus = container.querySelector("#pointsEditStatus");
      this.pointsEditSaveButton = container.querySelector("#pointsEditSave");
      this.pointsEditExitButton = container.querySelector("#pointsEditExit");
      this.pointsRedeemOverlay = container.querySelector("#pointsRedeemOverlay");
      this.pointsRedeemInput = container.querySelector("#pointsRedeemInput");
      this.pointsRedeemStatus = container.querySelector("#pointsRedeemStatus");
      this.pointsRedeemSubmitButton = container.querySelector("#pointsRedeemSubmit");
      this.pointsRedeemCancelButton = container.querySelector("#pointsRedeemCancel");

      this.hoverTooltip = document.createElement("div");
      this.hoverTooltip.className = "points-shop-floating-tooltip";
      this.hoverTooltip.hidden = true;
      this.hoverTooltip.innerHTML = `
        <div class="points-shop-floating-tooltip-title"></div>
        <div class="points-shop-floating-tooltip-body"></div>
      `;
      this.layer.appendChild(this.hoverTooltip);
      this.hoverTooltipTitle = this.hoverTooltip.querySelector(".points-shop-floating-tooltip-title");
      this.hoverTooltipBody = this.hoverTooltip.querySelector(".points-shop-floating-tooltip-body");

      this.toastLayer = document.createElement("div");
      this.toastLayer.className = "points-toast-layer";
      this.root.appendChild(this.toastLayer);

      if (this.badgeButton) {
        const badgeIndicator = document.createElement("span");
        badgeIndicator.className = "points-badge-notification";
        badgeIndicator.hidden = true;
        this.badgeButton.appendChild(badgeIndicator);
        this.badgeNotificationEl = badgeIndicator;
      } else {
        this.badgeNotificationEl = null;
      }

      if (this.inventoryTabButton) {
        const tabIndicator = document.createElement("span");
        tabIndicator.className = "points-shop-tab-notification";
        tabIndicator.hidden = true;
        this.inventoryTabButton.appendChild(tabIndicator);
        this.inventoryTabNotificationEl = tabIndicator;
      } else {
        this.inventoryTabNotificationEl = null;
      }
    }

    _bindEvents() {
      this.badgeButton.addEventListener("click", () => {
        if (this._badgeClickTimer) {
          clearTimeout(this._badgeClickTimer);
        }
        this._badgeClickTimer = setTimeout(() => {
          this._badgeClickTimer = null;
          this._sendUiCommand("toggle_points_shop");
          this.badgeButton.classList.remove("clicked");
          this.badgeButton.offsetWidth;
          this.badgeButton.classList.add("clicked");
        }, 220);
      });

      this.badgeButton.addEventListener("dblclick", (event) => {
        event.preventDefault();
        if (this._badgeClickTimer) {
          clearTimeout(this._badgeClickTimer);
          this._badgeClickTimer = null;
        }
        this._openPointsEditModal();
      });

      this.closeButton.addEventListener("click", () => this._sendUiCommand("close_points_shop"));
      this.backdrop.addEventListener("click", () => this._sendUiCommand("close_points_shop"));

      this.undoButton.addEventListener("click", async () => {
        await this._sendCommand("undo_last", {});
      });

      if (this.redeemOpenButton) {
        this.redeemOpenButton.addEventListener("click", () => {
          this._openRedeemModal();
        });
      }

      if (this.pointsRedeemOverlay) {
        this.pointsRedeemOverlay.addEventListener("click", (event) => {
          if (event.target === this.pointsRedeemOverlay) {
            this._closeRedeemModal();
          }
        });
      }

      if (this.pointsRedeemSubmitButton) {
        this.pointsRedeemSubmitButton.addEventListener("click", async () => {
          await this._submitRedeemCode();
        });
      }

      if (this.pointsRedeemCancelButton) {
        this.pointsRedeemCancelButton.addEventListener("click", () => {
          this._closeRedeemModal();
        });
      }

      if (this.pointsRedeemInput) {
        this.pointsRedeemInput.addEventListener("keydown", async (event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            await this._submitRedeemCode();
          }
        });
      }

      if (this.pointsEditOverlay) {
        this.pointsEditOverlay.addEventListener("click", (event) => {
          if (event.target === this.pointsEditOverlay) {
            this._closePointsEditModal();
          }
        });
      }

      if (this.pointsEditSaveButton) {
        this.pointsEditSaveButton.addEventListener("click", async () => {
          await this._savePointsEdit();
        });
      }

      if (this.pointsEditExitButton) {
        this.pointsEditExitButton.addEventListener("click", () => {
          this._closePointsEditModal();
        });
      }

      if (this.pointsEditInput) {
        this.pointsEditInput.addEventListener("keydown", async (event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            await this._savePointsEdit();
          }
        });
      }

      const onViewScroll = () => {
        this._scheduleViewSync();
      };
      if (this.rewardsEl) {
        this.rewardsEl.addEventListener("scroll", onViewScroll, { passive: true });
      }
      if (this.inventoryEl) {
        this.inventoryEl.addEventListener("scroll", onViewScroll, { passive: true });
      }
      if (this.historyEl) {
        this.historyEl.addEventListener("scroll", onViewScroll, { passive: true });
      }

      for (const button of this.tabButtons) {
        button.addEventListener("click", () => {
          const tab = String(button.dataset.tab || "shop");
          this._setActiveTab(tab);
        });
      }

      document.addEventListener("keydown", (event) => {
        if (!this.modalOpen) {
          return;
        }

        if (event.key === "Escape") {
          if (this.redeemModalOpen) {
            event.preventDefault();
            this._closeRedeemModal();
            return;
          }
          if (this.pointsEditOpen) {
            event.preventDefault();
            this._closePointsEditModal();
            return;
          }
          event.preventDefault();
          this._sendUiCommand("close_points_shop");
          return;
        }

        if (event.key === "Tab") {
          const focusables = this._focusableNodes();
          if (focusables.length === 0) {
            event.preventDefault();
            return;
          }

          const currentIndex = focusables.indexOf(document.activeElement);
          let nextIndex = currentIndex;
          if (event.shiftKey) {
            nextIndex = currentIndex <= 0 ? focusables.length - 1 : currentIndex - 1;
          } else {
            nextIndex = currentIndex >= focusables.length - 1 ? 0 : currentIndex + 1;
          }
          event.preventDefault();
          focusables[nextIndex].focus();
        }
      });
    }

    _focusableNodes() {
      return Array.from(
        this.modal.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      );
    }

    open() {
      if (this.modalOpen) {
        return;
      }
      this.lastFocused = document.activeElement;
      this.modalOpen = true;
      this.layer.classList.add("open");
      this.modal.focus();
      this.log("points_modal_open", { points: this.state.current_points });
    }

    close() {
      if (!this.modalOpen) {
        return;
      }
      this.modalOpen = false;
      this.layer.classList.remove("open");
      this.pendingConfirmItem = null;
      this.confirmEl.classList.remove("open");
      this.confirmEl.replaceChildren();
      this._hideRewardTooltip();
      if (this.lastFocused && typeof this.lastFocused.focus === "function") {
        this.lastFocused.focus();
      }
      this.log("points_modal_close", {});
    }

    _openPointsEditModal() {
      if (!this.pointsEditOverlay || !this.pointsEditInput) {
        return;
      }
      this.pointsEditOpen = true;
      this.pointsEditOverlay.hidden = false;
      this.pointsEditInput.value = String(Math.max(0, Number(this.state.current_points || 0)));
      this._setPointsEditStatus("", false);
      this.pointsEditInput.focus();
      this.pointsEditInput.select();
    }

    _closePointsEditModal() {
      if (!this.pointsEditOverlay) {
        return;
      }
      this.pointsEditOpen = false;
      this.pointsEditOverlay.hidden = true;
      this._setPointsEditStatus("", false);
    }

    _openRedeemModal() {
      if (!this.pointsRedeemOverlay || !this.pointsRedeemInput) {
        return;
      }
      this.redeemModalOpen = true;
      this.pointsRedeemOverlay.hidden = false;
      this.pointsRedeemInput.value = "";
      this._setRedeemStatus("", false);
      this.pointsRedeemInput.focus();
    }

    _closeRedeemModal() {
      if (!this.pointsRedeemOverlay) {
        return;
      }
      this.redeemModalOpen = false;
      this.pointsRedeemOverlay.hidden = true;
      this.redeemInFlight = false;
      if (this.pointsRedeemSubmitButton) {
        this.pointsRedeemSubmitButton.disabled = false;
      }
      if (this.pointsRedeemCancelButton) {
        this.pointsRedeemCancelButton.disabled = false;
      }
      this._setRedeemStatus("", false);
    }

    _setRedeemStatus(message, isError) {
      if (!this.pointsRedeemStatus) {
        return;
      }
      this.pointsRedeemStatus.textContent = String(message || "");
      this.pointsRedeemStatus.classList.toggle("is-error", Boolean(isError));
    }

    async _submitRedeemCode() {
      if (this.redeemInFlight) {
        return;
      }
      if (!this.pointsRedeemInput) {
        return;
      }
      const raw = String(this.pointsRedeemInput.value || "");
      const trimmed = raw.trim();
      if (!trimmed) {
        this._setRedeemStatus("Enter a redemption code.", true);
        return;
      }

      this.redeemInFlight = true;
      if (this.pointsRedeemSubmitButton) {
        this.pointsRedeemSubmitButton.disabled = true;
      }
      if (this.pointsRedeemCancelButton) {
        this.pointsRedeemCancelButton.disabled = true;
      }
      this._setRedeemStatus("Redeeming...", false);

      const result = await this._sendCommand("redeem_code", { code: trimmed });
      const ok = Boolean(result && result.ok);
      if (!ok) {
        const err = String((result && (result.error || result.message)) || "Invalid code");
        this._setRedeemStatus(err, true);
      } else {
        const code = String((result && result.code) || trimmed).trim();
        const points = Math.max(0, Number((result && result.points_awarded) || 0));
        const awards = Array.isArray(result && result.awards_granted) ? result.awards_granted : [];
        if (points > 0) {
          this._queueToast(`+${Math.floor(points)} Points - Code ${code}`, "points");
        }
        for (const award of awards) {
          const label = String(award || "").trim();
          if (!label) {
            continue;
          }
          this._queueToast(`Unlocked ${label}`, "reward");
        }
        this.pointsRedeemInput.value = "";
        this._closeRedeemModal();
      }

      this.redeemInFlight = false;
      if (this.pointsRedeemSubmitButton) {
        this.pointsRedeemSubmitButton.disabled = false;
      }
      if (this.pointsRedeemCancelButton) {
        this.pointsRedeemCancelButton.disabled = false;
      }
    }

    _setPointsEditStatus(message, isError) {
      if (!this.pointsEditStatus) {
        return;
      }
      this.pointsEditStatus.textContent = String(message || "");
      this.pointsEditStatus.classList.toggle("is-error", Boolean(isError));
    }

    async _savePointsEdit() {
      if (!this.pointsEditInput) {
        return;
      }
      if (typeof this.onCommand !== "function") {
        this._setPointsEditStatus("Live tracker command handler is unavailable.", true);
        return;
      }

      const raw = String(this.pointsEditInput.value || "").trim();
      const parsed = Number(raw);
      if (!Number.isFinite(parsed) || parsed < 0) {
        this._setPointsEditStatus("Enter a valid non-negative number.", true);
        return;
      }

      const target = Math.floor(parsed);
      const result = await this.onCommand("set_points_total", {
        amount: target,
        source: "manual_points_chip_edit",
      });

      if (result && result.state) {
        this.setState(result.state);
      }
      if (result && result.overlay_ui) {
        this.applyOverlayUiState(result.overlay_ui, "command_response");
      }

      if (!result || !result.ok) {
        this._setPointsEditStatus(String((result && result.message) || "Failed to save points."), true);
        return;
      }

      this._setPointsEditStatus("Points saved.", false);
      this._closePointsEditModal();
    }

    _setActiveTab(tab, options) {
      const opts = options && typeof options === "object" ? options : {};
      const nextTab = ["shop", "inventory", "log"].includes(tab) ? tab : "shop";
      this.activeTab = nextTab;

      for (const button of this.tabButtons) {
        const isActive = String(button.dataset.tab || "") === nextTab;
        button.classList.toggle("is-active", isActive);
        if (isActive) {
          button.setAttribute("aria-current", "page");
        } else {
          button.removeAttribute("aria-current");
        }
      }

      for (const panel of this.tabPanels) {
        const isActive = String(panel.dataset.panel || "") === nextTab;
        panel.classList.toggle("is-active", isActive);
      }

      this.log("points_tab_switch", { tab: nextTab });

      if (nextTab === "inventory") {
        this._ackInventoryNotifications();
      }

      if (!opts.skipSync) {
        this._scheduleViewSync();
      }
    }

    setPurchaseLockDuringBattle(locked) {
      const next = Boolean(locked);
      if (this.purchaseLockedDuringBattle === next) {
        return;
      }
      this.purchaseLockedDuringBattle = next;
      this._render();
    }

    _purchaseLockMessage() {
      return "Cannot purchase while in battle. You can still use inventory rewards.";
    }

    _notifyPurchaseLocked() {
      const now = Date.now();
      if (now - this._lastPurchaseLockToastAt < 1200) {
        return;
      }
      this._lastPurchaseLockToastAt = now;
      this._queueToast(this._purchaseLockMessage(), "points");
    }

    applyOverlayUiState(nextOverlayUi, source) {
      if (!nextOverlayUi || typeof nextOverlayUi !== "object") {
        return;
      }

      const desiredOpen = Boolean(nextOverlayUi.points_shop_open);
      const currentOpen = Boolean(this.modalOpen);
      this.overlayUi = {
        points_shop_open: desiredOpen,
        points_shop_tab: String(nextOverlayUi.points_shop_tab || "shop"),
        points_shop_scroll_top: Number(nextOverlayUi.points_shop_scroll_top || 0),
        points_shop_last_changed_by: nextOverlayUi.points_shop_last_changed_by || null,
        points_shop_changed_at: Number(nextOverlayUi.points_shop_changed_at || 0),
      };

      const nextTab = ["shop", "inventory", "log"].includes(String(this.overlayUi.points_shop_tab || ""))
        ? String(this.overlayUi.points_shop_tab)
        : "shop";
      const nextScrollTop = Math.max(0, Math.floor(Number(this.overlayUi.points_shop_scroll_top || 0)));

      if (desiredOpen === currentOpen) {
        if (desiredOpen) {
          this._applySyncedView(nextTab, nextScrollTop);
        }
        return;
      }

      if (desiredOpen) {
        this.open();
        this._applySyncedView(nextTab, nextScrollTop);
      } else {
        this.close();
      }

      this.log("points_modal_sync_applied", {
        source: source || "unknown",
        points_shop_open: desiredOpen,
        points_shop_last_changed_by: this.overlayUi.points_shop_last_changed_by,
        points_shop_changed_at: this.overlayUi.points_shop_changed_at,
      });
    }

    setState(nextState) {
      if (!nextState || typeof nextState !== "object") {
        return;
      }

      const previousInventorySize = Array.isArray(this.state.inventory) ? this.state.inventory.length : 0;
      const incomingTransactions = Array.isArray(nextState.transactions) ? nextState.transactions : [];
      const newTransactions = [];
      let hasPurchase = false;
      let hasRedeem = false;

      if (!this._stateInitialized) {
        const seedIds = incomingTransactions
          .map((txn) => String(txn.id || ""))
          .filter((value) => Boolean(value));
        this._seenTxnIds = new Set(seedIds);
        this._toastedTxnIds = new Set(seedIds);
        this._stateInitialized = true;
      } else {
        for (const txn of incomingTransactions) {
          const txnId = String(txn.id || "");
          if (!txnId || this._seenTxnIds.has(txnId)) {
            continue;
          }
          newTransactions.push(txn);
        }
        if (incomingTransactions.length > 0) {
          const nextSeenIds = incomingTransactions
            .map((txn) => String(txn.id || ""))
            .filter((value) => Boolean(value));
          this._seenTxnIds = new Set(nextSeenIds);
        }
      }

      this.state = {
        ...defaultState(),
        ...nextState,
        inventory: Array.isArray(nextState.inventory) ? nextState.inventory : [],
        unseen_inventory_reward_ids: Array.isArray(nextState.unseen_inventory_reward_ids)
          ? nextState.unseen_inventory_reward_ids
          : [],
        unseen_inventory_reward_count: Number(nextState.unseen_inventory_reward_count || 0),
        transactions: Array.isArray(nextState.transactions) ? nextState.transactions : [],
      };
      this._render();

      if (this.state.inventory.length !== previousInventorySize) {
        this.log("points_inventory_update", {
          inventory_count: this.state.inventory.length,
          previous_inventory_count: previousInventorySize,
        });
      }

      const toastEvents = [];
      for (const txn of newTransactions) {
        const txnId = String(txn.id || "");
        if (txnId && this._toastedTxnIds.has(txnId)) {
          continue;
        }

        const txnType = String(txn.type || "");
        if (txnType === "purchase") {
          hasPurchase = true;
        }
        if (txnType === "redeem") {
          hasRedeem = true;
        }

        const metadata = txn.metadata && typeof txn.metadata === "object" ? txn.metadata : {};
        if (txnType === "award_revoke") {
          const revokedTrainerId = String(metadata.trainer_id || "").trim();
          if (revokedTrainerId) {
            this._cancelPendingTrainerToast(revokedTrainerId);
          }
          continue;
        }

        if (txnType === "award") {
          const source = String(metadata.source || "").trim();
          const trainerId = String(metadata.trainer_id || "").trim();
          const points = Math.max(0, Math.abs(Number(txn.cost || 0)));
          if (source !== "trainer_reward" || !trainerId || points <= 0 || !txnId) {
            continue;
          }

          const trainerName = String(metadata.trainer_name || metadata.trainer_id || "Trainer");
          this._schedulePendingTrainerToast({
            trainerId,
            trainerName,
            points,
            txnId,
          });
          continue;
        }
      }

      toastEvents.sort((left, right) => {
        if (left.timestamp !== right.timestamp) {
          return left.timestamp - right.timestamp;
        }
        return left.priority - right.priority;
      });

      for (const event of toastEvents) {
        this._queueToast(event.message, event.tone);
        const eventTxnId = String((event.txn && event.txn.id) || "");
        if (eventTxnId) {
          this._toastedTxnIds.add(eventTxnId);
        }
        this.log("points_notification_render", {
          txn_id: String(event.txn.id || ""),
          message: event.message,
          tone: event.tone,
        });
      }

      if (hasPurchase) {
        this._triggerPurchaseFlash();
      }
      if (hasRedeem || this.state.inventory.length < previousInventorySize) {
        this._triggerInventoryPulse();
      }
    }

    _cancelPendingTrainerToast(trainerId) {
      const key = String(trainerId || "").trim();
      if (!key) {
        return;
      }
      const pending = this._pendingTrainerToasts.get(key);
      if (!pending) {
        return;
      }
      clearTimeout(pending.timerId);
      this._pendingTrainerToasts.delete(key);
    }

    _schedulePendingTrainerToast(payload) {
      const trainerId = String(payload && payload.trainerId || "").trim();
      const trainerName = String(payload && payload.trainerName || "Trainer").trim() || "Trainer";
      const points = Math.max(0, Number(payload && payload.points || 0));
      const txnId = String(payload && payload.txnId || "").trim();
      if (!trainerId || !txnId || points <= 0) {
        return;
      }

      this._cancelPendingTrainerToast(trainerId);
      const timerId = setTimeout(() => {
        const currentAwarded = Array.isArray(this.state.awarded_trainers) ? this.state.awarded_trainers : [];
        const stillAwarded = currentAwarded.some((value) => String(value || "").trim() === trainerId);
        if (!stillAwarded || this._toastedTxnIds.has(txnId)) {
          this._pendingTrainerToasts.delete(trainerId);
          return;
        }

        const message = `+${Math.floor(points)} Points - ${trainerName} Defeated`;
        this._queueToast(message, "points");
        this._toastedTxnIds.add(txnId);
        this.log("points_notification_render", {
          txn_id: txnId,
          message,
          tone: "points",
          trainer_id: trainerId,
          delayed_confirmed: true,
        });
        this._pendingTrainerToasts.delete(trainerId);
      }, 1400);

      this._pendingTrainerToasts.set(trainerId, {
        timerId,
        txnId,
      });
    }

    _render() {
      const pointsText = this.previewPointsText != null
        ? String(this.previewPointsText)
        : String(this.state.current_points || 0);
      this.badgeValue.textContent = pointsText;
      if (this.badgeButton) {
        const digitsOnly = pointsText.replace(/[^0-9]/g, "");
        const length = Math.max(1, digitsOnly.length);
        const mode = length <= 1 ? "single" : length === 2 ? "double" : "multi";
        this.badgeButton.dataset.digits = mode;
      }
      this.balanceEl.textContent = String(this.state.current_points || 0);
      this._renderNotificationBadges();

      this._renderRewards();
      this._renderInventory();
      this._renderHistory();
    }

    setPreviewPoints(value) {
      if (value == null || String(value).trim() === "") {
        this.previewPointsText = null;
      } else {
        this.previewPointsText = String(value).trim();
      }
      this._render();
    }

    _renderRewards() {
      this.rewardsEl.replaceChildren();
      const groupedItems = new Map();
      for (const category of CATEGORY_ORDER) {
        groupedItems.set(category, []);
      }

      for (const item of SHOP_ITEMS) {
        if (item.purchasable === false) {
          continue;
        }
        const category = CATEGORY_ORDER.includes(item.category) ? item.category : "Events";
        groupedItems.get(category).push(item);
      }

      for (const category of CATEGORY_ORDER) {
        const items = groupedItems.get(category) || [];

        const slug = this._categorySlug(category);
        const group = document.createElement("section");
        group.className = `points-shop-category points-shop-category-${slug}`;

        const banner = document.createElement("header");
        banner.className = "points-shop-category-banner";
        banner.innerHTML = `<span>${category}</span>`;

        const grid = document.createElement("div");
        grid.className = "points-shop-category-grid";

        if (!items.length) {
          const empty = document.createElement("p");
          empty.className = "points-shop-empty points-shop-category-empty";
          empty.textContent = "No rewards available in this section yet.";
          grid.appendChild(empty);
        } else {
          for (const item of items) {
            const tier = this._costTier(item.cost);
            const card = document.createElement("button");
            card.type = "button";
            card.className = `points-shop-reward-card points-shop-tier-${tier}`;
            card.setAttribute("aria-label", `Purchase ${item.name} for ${item.cost} points`);
            const canAfford = Number(this.state.current_points || 0) >= item.cost;
            const remainingStock = this._stockRemaining(item.id);
            const soldOut = remainingStock === 0;
            const battleLocked = this.purchaseLockedDuringBattle;
            card.disabled = soldOut || battleLocked;
            if (!canAfford) {
              card.classList.add("is-unaffordable");
            }
            if (soldOut) {
              card.classList.add("is-sold-out");
            }
            if (battleLocked) {
              card.classList.add("is-unaffordable");
              card.title = this._purchaseLockMessage();
            }
            card.addEventListener("click", () => {
              if (battleLocked) {
                this._notifyPurchaseLocked();
                return;
              }
              if (!canAfford || soldOut) {
                return;
              }
              this._showConfirm(item);
            });

            card.addEventListener("mouseenter", () => this._showRewardTooltip(item, card));
            card.addEventListener("focus", () => this._showRewardTooltip(item, card));
            card.addEventListener("mouseleave", () => this._hideRewardTooltip());
            card.addEventListener("blur", () => this._hideRewardTooltip());

            const icon = document.createElement("img");
            icon.className = "points-shop-reward-card-image";
            icon.alt = `${item.name} reward card`;
            icon.decoding = "async";
            icon.loading = "lazy";
            icon.hidden = true;

            const fallback = document.createElement("div");
            fallback.className = "points-shop-reward-card-fallback";

            const stockChip = document.createElement("div");
            stockChip.className = "points-shop-stock-chip";
            if (remainingStock != null) {
              stockChip.textContent = `${remainingStock} left`;
              if (remainingStock <= 0) {
                stockChip.classList.add("is-empty");
              }
            } else {
              stockChip.textContent = "∞";
            }

            this._attachRewardImage(icon, fallback, item);

            card.append(icon, fallback, stockChip);
            grid.appendChild(card);
          }
        }

        group.append(banner, grid);
        this.rewardsEl.appendChild(group);
      }
    }

    _renderInventory() {
      this.inventoryEl.replaceChildren();

      const inventory = Array.isArray(this.state.inventory) ? [...this.state.inventory] : [];
      inventory.sort((left, right) => this._inventorySortKey(left).localeCompare(this._inventorySortKey(right)));

      if (!inventory.length) {
        const empty = document.createElement("p");
        empty.className = "points-shop-empty";
        empty.textContent = "No purchased rewards yet.";
        this.inventoryEl.appendChild(empty);
        return;
      }

      for (const entry of inventory) {
        const card = document.createElement("div");
        card.className = "points-shop-inventory-card";

        const imageWrap = document.createElement("div");
        imageWrap.className = "points-shop-inventory-image-wrap";

        const icon = document.createElement("img");
        icon.className = "points-shop-inventory-image";
        icon.alt = `${entry.name || entry.type || "Reward"} inventory card`;
        icon.decoding = "async";
        icon.loading = "lazy";
        icon.hidden = true;

        const fallback = document.createElement("div");
        fallback.className = "points-shop-reward-card-fallback points-shop-inventory-fallback";

        const inventoryItem = this._inventoryEntryItem(entry);
        this._attachRewardImage(icon, fallback, inventoryItem);

        card.addEventListener("mouseenter", () => this._showRewardTooltip(inventoryItem, card));
        card.addEventListener("mouseleave", () => this._hideRewardTooltip());
        card.addEventListener("focusin", () => this._showRewardTooltip(inventoryItem, card));
        card.addEventListener("focusout", (event) => {
          if (card.contains(event.relatedTarget)) {
            return;
          }
          this._hideRewardTooltip();
        });

        const actions = document.createElement("div");
        actions.className = "points-shop-inventory-actions";

        const redeemBtn = document.createElement("button");
        redeemBtn.type = "button";
        redeemBtn.className = "points-shop-inventory-redeem";
        redeemBtn.textContent = "Redeem";
        redeemBtn.addEventListener("click", async () => {
          await this._sendCommand("redeem", { inventory_id: entry.id });
        });

        const sellBtn = document.createElement("button");
        sellBtn.type = "button";
        sellBtn.className = "points-shop-inventory-sell";
        sellBtn.textContent = "Sell";
        sellBtn.addEventListener("click", () => {
          const refund = this._sellRefundForEntry(entry);
          this._showActionConfirm({
            message: `Sell ${entry.name || "Reward"} for ${refund} points?`,
            confirmLabel: "Sell",
            cancelLabel: "Cancel",
            confirmClassName: "points-shop-confirm-sell",
            cancelClassName: "points-shop-confirm-cancel",
            onConfirm: async () => {
              await this._sendCommand("sell", { inventory_id: entry.id });
            },
          });
        });

        imageWrap.append(icon, fallback);
        actions.append(redeemBtn, sellBtn);
        card.append(imageWrap, actions);
        this.inventoryEl.appendChild(card);
      }
    }

    _inventoryEntryItem(entry) {
      const itemId = String(entry.item_id || entry.type || "");
      const definition = SHOP_ITEM_MAP.get(itemId) || null;
      return {
        id: itemId,
        name: String(entry.name || (definition && definition.name) || entry.type || "Reward"),
        cost: Number(entry.base_cost || (definition && definition.cost) || 0),
        description: String((definition && definition.description) || ""),
      };
    }

    _inventorySortKey(entry) {
      const itemId = String(entry.item_id || entry.type || "");
      const fileHint = REWARD_IMAGE_FILE_HINTS[itemId];
      if (fileHint) {
        return fileHint.toLowerCase();
      }
      return String(entry.name || itemId || "zzzz").toLowerCase();
    }

    _sellRefundForEntry(entry) {
      const itemId = String(entry.item_id || entry.type || "");
      const sourceCost = Number(
        entry.base_cost != null
          ? entry.base_cost
          : SHOP_ITEMS.find((item) => item.id === itemId)?.cost || 0
      );
      const baseCost = Number.isFinite(sourceCost) ? Math.max(0, Math.floor(sourceCost)) : 0;
      if (baseCost <= 0) {
        return 0;
      }
      return Math.max(1, Math.floor(baseCost / 2));
    }

    _unseenRewardCount() {
      const fromCount = Number(this.state.unseen_inventory_reward_count || 0);
      if (Number.isFinite(fromCount) && fromCount > 0) {
        return Math.floor(fromCount);
      }
      const unseenIds = Array.isArray(this.state.unseen_inventory_reward_ids)
        ? this.state.unseen_inventory_reward_ids
        : [];
      return unseenIds.length;
    }

    _renderNotificationBadges() {
      const count = this._unseenRewardCount();
      const show = count > 0;

      if (this.badgeNotificationEl) {
        this.badgeNotificationEl.hidden = !show;
        this.badgeNotificationEl.textContent = count > 9 ? "9+" : String(count);
      }

      if (this.inventoryTabNotificationEl) {
        this.inventoryTabNotificationEl.hidden = !show;
        this.inventoryTabNotificationEl.textContent = count > 9 ? "9+" : String(count);
      }
    }

    async _ackInventoryNotifications() {
      if (this._inventoryAckInFlight) {
        return;
      }
      if (this._unseenRewardCount() <= 0) {
        return;
      }

      this._inventoryAckInFlight = true;
      try {
        await this._sendCommand("ack_inventory_notifications", {});
      } finally {
        this._inventoryAckInFlight = false;
      }
    }

    _stockRemaining(itemId) {
      const stock = this.state && typeof this.state.stock_remaining === "object"
        ? this.state.stock_remaining
        : null;
      const fromState = stock && stock[itemId] != null ? Number(stock[itemId]) : null;
      if (Number.isFinite(fromState)) {
        return Math.max(0, Math.floor(fromState));
      }
      const fallback = STOCK_LIMITS[itemId];
      if (fallback == null) {
        return null;
      }
      return Math.max(0, Math.floor(Number(fallback) || 0));
    }

    _costTier(cost) {
      const value = Number(cost || 0);
      if (value <= 2) {
        return "common";
      }
      if (value <= 4) {
        return "rare";
      }
      return "epic";
    }

    _categorySlug(category) {
      return String(category || "events").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
    }

    _rewardImageCandidates(item) {
      const names = [];
      const fileHint = REWARD_IMAGE_FILE_HINTS[item.id];
      if (fileHint) {
        names.push(fileHint);
      }

      const normalized = String(item.name || "")
        .replace(/\+/g, "")
        .replace(/\s*[-–]\s*/g, " ")
        .replace(/\s+/g, " ")
        .trim();

      if (normalized) {
        names.push(`${normalized}.png`);
        names.push(`${normalized}.webp`);
        names.push(`${normalized}.jpg`);

        const compact = normalized.replace(/\s+/g, "");
        names.push(`${compact}.png`);
      }

      const unique = [];
      const seen = new Set();
      for (const fileName of names) {
        if (!fileName || seen.has(fileName)) {
          continue;
        }
        seen.add(fileName);
        unique.push(`${REWARD_IMAGE_BASE_PATH}/${fileName}`);
      }
      return unique;
    }

    async _attachRewardImage(iconNode, fallbackNode, item) {
      const candidates = this._rewardImageCandidates(item);
      for (const candidate of candidates) {
        const keyed = await this._getKeyedImageSource(candidate);
        if (!keyed) {
          continue;
        }

        iconNode.src = keyed;
        iconNode.hidden = false;
        fallbackNode.hidden = true;
        return;
      }

      iconNode.hidden = true;
      fallbackNode.hidden = false;
    }

    async _getKeyedImageSource(src) {
      if (!src) {
        return null;
      }
      if (this._transparentImageCache.has(src)) {
        return this._transparentImageCache.get(src);
      }
      if (this._imageLoadFailures.has(src)) {
        return null;
      }

      try {
        await this._loadImageElement(src);
        // Keep source art intact; aggressive color-keying caused detached footer artifacts.
        this._transparentImageCache.set(src, src);
        return src;
      } catch (_error) {
        this._imageLoadFailures.add(src);
        return null;
      }
    }

    _loadImageElement(src) {
      return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error(`Failed to load image: ${src}`));
        image.src = src;
      });
    }

    _itemMonogram(name) {
      const words = String(name || "Reward")
        .split(/\s+/)
        .map((part) => part.trim())
        .filter(Boolean);
      if (!words.length) {
        return "R";
      }
      if (words.length === 1) {
        return words[0].slice(0, 2).toUpperCase();
      }
      return `${words[0][0] || ""}${words[1][0] || ""}`.toUpperCase();
    }

    _renderHistory() {
      this.historyEl.replaceChildren();
      const history = [...this.state.transactions].reverse();

      if (!history.length) {
        const empty = document.createElement("p");
        empty.className = "points-shop-empty";
        empty.textContent = "No transactions yet.";
        this.historyEl.appendChild(empty);
        return;
      }

      for (const txn of history.slice(0, 30)) {
        const row = document.createElement("div");
        row.className = "points-shop-history-item";
        if (txn.undone) {
          row.classList.add("undone");
        }

        const label = document.createElement("div");
        label.className = "points-shop-history-label";
        label.textContent = `${txn.type}: ${txn.item} (${txn.cost} pts)`;

        const detail = document.createElement("div");
        detail.className = "points-shop-history-meta";
        detail.textContent = `${nowIso(Number(txn.timestamp))} | ${txn.points_before} -> ${txn.points_after}`;

        row.append(label, detail);
        this.historyEl.appendChild(row);
      }
    }

    _showConfirm(item) {
      if (this.purchaseLockedDuringBattle) {
        this._notifyPurchaseLocked();
        return;
      }

      this.pendingConfirmItem = item;
      this._showActionConfirm({
        message: `Purchase ${item.name} for ${item.cost} points?`,
        confirmLabel: "Confirm",
        cancelLabel: "Cancel",
        confirmClassName: "points-shop-confirm-accept",
        cancelClassName: "points-shop-confirm-cancel",
        onConfirm: async () => {
          await this._sendCommand("purchase", { item_id: item.id });
          this.pendingConfirmItem = null;
        },
      });
    }

    _showActionConfirm(options) {
      this.confirmEl.replaceChildren();
      this.confirmEl.classList.add("open");

      const card = document.createElement("div");
      card.className = "points-shop-confirm-dialog";

      const text = document.createElement("p");
      text.textContent = String(options.message || "Are you sure?");

      const actions = document.createElement("div");
      actions.className = "points-shop-confirm-actions";

      const confirmBtn = document.createElement("button");
      confirmBtn.type = "button";
      confirmBtn.textContent = String(options.confirmLabel || "Confirm");
      confirmBtn.className = `points-shop-confirm-btn ${String(options.confirmClassName || "points-shop-confirm-accept")}`;

      const cancelBtn = document.createElement("button");
      cancelBtn.type = "button";
      cancelBtn.textContent = String(options.cancelLabel || "Cancel");
      cancelBtn.className = `points-shop-confirm-btn ${String(options.cancelClassName || "points-shop-confirm-cancel")}`;

      confirmBtn.addEventListener("click", async () => {
        if (typeof options.onConfirm === "function") {
          await options.onConfirm();
        }
        this.confirmEl.classList.remove("open");
        this.confirmEl.replaceChildren();
      });

      cancelBtn.addEventListener("click", () => {
        this.confirmEl.classList.remove("open");
        this.confirmEl.replaceChildren();
      });

      actions.append(confirmBtn, cancelBtn);
      card.append(text, actions);
      this.confirmEl.append(card);
    }

    _showRewardTooltip(item, card) {
      if (!this.hoverTooltip) {
        return;
      }
      this.hoverTooltipTitle.textContent = "";
      this.hoverTooltipBody.textContent = String(item.description || "");

      this.hoverTooltip.hidden = false;
      this._positionRewardTooltip(card);
    }

    _positionRewardTooltip(card) {
      if (!this.hoverTooltip || this.hoverTooltip.hidden || !card) {
        return;
      }

      const cardRect = card.getBoundingClientRect();
      const tooltipRect = this.hoverTooltip.getBoundingClientRect();
      const offset = 12;

      const isGridLast = Boolean(card.parentElement && card.parentElement.lastElementChild === card);
      const preferLeft =
        this._isLastRewardInRow(card) ||
        isGridLast ||
        (cardRect.right + tooltipRect.width + offset > window.innerWidth - 8);
      let left = preferLeft
        ? (cardRect.left - tooltipRect.width - offset - 56)
        : (cardRect.right + offset);
      let top = cardRect.top + ((cardRect.height - tooltipRect.height) / 2);

      const minLeft = 8;
      const maxLeft = window.innerWidth - tooltipRect.width - 8;
      const minTop = 8;
      const maxTop = window.innerHeight - tooltipRect.height - 8;

      left = Math.max(minLeft, Math.min(left, maxLeft));
      top = Math.max(minTop, Math.min(top, maxTop));

      this.hoverTooltip.style.left = `${Math.round(left)}px`;
      this.hoverTooltip.style.top = `${Math.round(top)}px`;
    }

    _isLastRewardInRow(card) {
      const grid = card && card.parentElement;
      if (!grid) {
        return false;
      }

      const cardRect = card.getBoundingClientRect();
      const all = Array.from(grid.querySelectorAll(".points-shop-reward-card"));
      const rowCards = all.filter((node) => {
        const rect = node.getBoundingClientRect();
        return Math.abs(rect.top - cardRect.top) < 24;
      });

      if (!rowCards.length) {
        return false;
      }
      if (rowCards.length === 1) {
        return false;
      }

      const maxRight = Math.max(...rowCards.map((node) => node.getBoundingClientRect().right));
      return (maxRight - cardRect.right) < 12;
    }

    _hideRewardTooltip() {
      if (!this.hoverTooltip) {
        return;
      }
      this.hoverTooltip.hidden = true;
    }

    async _sendCommand(command, payload) {
      if (typeof this.onCommand !== "function") {
        this.log("points_command_no_handler", { command });
        return;
      }

      const result = await this.onCommand(command, payload || {});
      if (result && result.state) {
        this.setState(result.state);
      }

      this.log("points_command_result", {
        command,
        ok: Boolean(result && result.ok),
        message: result ? result.message : "",
      });

      if (result && result.overlay_ui) {
        this.applyOverlayUiState(result.overlay_ui, "command_response");
      }

      return result;
    }

    async _sendUiCommand(command, payload) {
      if (typeof this.onUiCommand !== "function") {
        this.log("points_ui_command_no_handler", { command });
        this._applyLegacyUiFallback(command, "no_handler");
        return;
      }

      const result = await this.onUiCommand(command, payload && typeof payload === "object" ? payload : {});
      this.log("points_ui_command_result", {
        command,
        ok: Boolean(result && result.ok),
        message: result ? result.message : "",
      });

      if (result && result.overlay_ui) {
        this.applyOverlayUiState(result.overlay_ui, "ui_command_response");
        return;
      }

      if (this._shouldApplyLegacyUiFallback(result)) {
        this._applyLegacyUiFallback(command, result ? String(result.message || "") : "unknown_error");
      }
    }

    _shouldApplyLegacyUiFallback(result) {
      if (!result || result.ok) {
        return false;
      }

      const message = String(result.message || "").toLowerCase();
      if (!message) {
        return false;
      }

      return (
        message.includes("unsupported points command") ||
        message.includes("unknown points command") ||
        message.includes("live tracker connection is required") ||
        message.includes("failed to send points command") ||
        message.includes("timed out")
      );
    }

    _applyLegacyUiFallback(command, reason) {
      let desiredOpen = this.modalOpen;
      if (command === "open_points_shop") {
        desiredOpen = true;
      } else if (command === "close_points_shop") {
        desiredOpen = false;
      } else if (command === "toggle_points_shop") {
        desiredOpen = !this.modalOpen;
      } else {
        return;
      }

      const fallbackState = {
        points_shop_open: desiredOpen,
        points_shop_last_changed_by: "legacy_client_fallback",
        points_shop_changed_at: Date.now(),
      };

      this.log("points_ui_command_legacy_fallback", {
        command,
        reason,
        points_shop_open: desiredOpen,
      });
      this.applyOverlayUiState(fallbackState, "legacy_fallback");
    }

    _activeScrollContainer() {
      if (this.activeTab === "inventory") {
        return this.inventoryEl || null;
      }
      if (this.activeTab === "log") {
        return this.historyEl || null;
      }
      return this.rewardsEl || this.contentEl || null;
    }

    _scheduleViewSync() {
      if (this._suppressViewSync || !this.modalOpen) {
        return;
      }
      clearTimeout(this._viewSyncTimer);
      this._viewSyncTimer = setTimeout(() => {
        this._viewSyncTimer = null;
        this._flushViewSync();
      }, 80);
    }

    _flushViewSync() {
      if (this._suppressViewSync || !this.modalOpen) {
        return;
      }
      const container = this._activeScrollContainer();
      const scrollTop = container ? Math.max(0, Math.floor(Number(container.scrollTop || 0))) : 0;
      this._sendUiCommand("sync_points_shop_view", {
        tab: this.activeTab,
        scroll_top: scrollTop,
      });
    }

    _applySyncedView(tab, scrollTop) {
      this._suppressViewSync = true;
      this._setActiveTab(tab, { skipSync: true });
      const container = this._activeScrollContainer();
      if (container) {
        container.scrollTop = Math.max(0, Math.floor(Number(scrollTop || 0)));
      }
      setTimeout(() => {
        this._suppressViewSync = false;
      }, 0);
    }

    _triggerPurchaseFlash() {
      if (!this.modal) {
        return;
      }
      this.modal.classList.remove("points-shop-purchase-flash");
      this.modal.offsetWidth;
      this.modal.classList.add("points-shop-purchase-flash");
      clearTimeout(this._purchaseFlashTimer);
      this._purchaseFlashTimer = setTimeout(() => {
        this.modal.classList.remove("points-shop-purchase-flash");
      }, 480);
    }

    _triggerInventoryPulse() {
      if (!this.inventoryEl) {
        return;
      }
      this.inventoryEl.classList.remove("points-shop-inventory-pulse");
      this.inventoryEl.offsetWidth;
      this.inventoryEl.classList.add("points-shop-inventory-pulse");
      clearTimeout(this._inventoryPulseTimer);
      this._inventoryPulseTimer = setTimeout(() => {
        this.inventoryEl.classList.remove("points-shop-inventory-pulse");
      }, 580);
    }

    _queueToast(message, tone) {
      this._toastQueue.push({
        message: String(message || ""),
        tone: tone === "reward" ? "reward" : "points",
      });
      this._drainToastQueue();
    }

    _drainToastQueue() {
      if (this._toastActive) {
        return;
      }
      const next = this._toastQueue.shift();
      if (!next) {
        return;
      }
      this._toastActive = true;
      this._showToast(next.message, next.tone, () => {
        this._toastActive = false;
        this._drainToastQueue();
      });
    }

    _showToast(message, tone, onDone) {
      if (!this.toastLayer) {
        if (typeof onDone === "function") {
          onDone();
        }
        return;
      }

      const toast = document.createElement("div");
      toast.className = "points-toast";
      if (tone === "reward") {
        toast.classList.add("points-toast-reward");
      } else {
        toast.classList.add("points-toast-points");
      }
      toast.textContent = message;
      this.toastLayer.appendChild(toast);

      requestAnimationFrame(() => {
        toast.classList.add("visible");
      });

      setTimeout(() => {
        toast.classList.remove("visible");
        setTimeout(() => {
          toast.remove();
          if (typeof onDone === "function") {
            onDone();
          }
        }, 240);
      }, 2400);
    }
  }

  window.PointsShopUI = PointsShopUI;
})();
