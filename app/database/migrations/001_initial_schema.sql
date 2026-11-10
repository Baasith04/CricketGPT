        -- =============================================================================
        -- CricketGPT Database Schema Migration 001: Initial Schema
        -- =============================================================================
        -- Target Database : Supabase PostgreSQL 15+
        -- Version         : 1.2.1 (Penalty Recipient Removed, Result Method Added)
        -- Architecture    : Pure Relational + JSONB Hybrid for IPL Cricket Data
        -- =============================================================================
        -- SAFE TRANSACTIONAL MATCH REPLACEMENT STRATEGY:
        -- Because child tables (deliveries, delivery_wickets) enforce ON DELETE RESTRICT
        -- against match_players to guarantee integrity, the Ingestion Service must execute
        -- an explicit bottom-up deletion order within a single transaction when replacing
        -- or correcting a previously imported match:
        --
        --   BEGIN;
        --     1. DELETE FROM delivery_wickets WHERE match_id = :match_id;
        --     2. DELETE FROM deliveries       WHERE match_id = :match_id;
        --     3. DELETE FROM match_awards     WHERE match_id = :match_id;
        --     4. DELETE FROM innings          WHERE match_id = :match_id;
        --     5. DELETE FROM match_players    WHERE match_id = :match_id;
        --     6. DELETE FROM match_teams      WHERE match_id = :match_id;
        --     7. DELETE FROM matches          WHERE match_id = :match_id;
        --
        --     -- Re-insert refreshed match and child records
        --     8. INSERT INTO matches (...) VALUES (...);
        --     9. INSERT INTO match_teams / match_players / match_awards / innings / deliveries / delivery_wickets;
        --
    --    10. Insert or update the sync_files tracking record.
    --        This operation handles both first-time imports and corrected matches.
    --
    --        The actual UPSERT will be executed by the Python ingestion service:
    --
    --        INSERT INTO sync_files (
    --            match_id,
    --            file_name,
    --            file_sha256,
    --            cricsheet_revision,
    --            status,
    --            last_synced_at
    --        )
    --        VALUES (
    --            :match_id,
    --            :file_name,
    --            :new_hash,
    --            :new_rev,
    --            'synced',
    --            NOW()
    --        )
    --        ON CONFLICT (match_id)
    --        DO UPDATE SET
    --            file_name = EXCLUDED.file_name,
    --            file_sha256 = EXCLUDED.file_sha256,
    --            cricsheet_revision = EXCLUDED.cricsheet_revision,
    --            status = 'updated',
    --            last_synced_at = NOW();
    --
    -- Preserves sync_files row, preserves append-only sync_history,
    -- and satisfies every ON DELETE RESTRICT constraint.
    -- =============================================================================
        -- =============================================================================

        -- =============================================================================
        -- TABLE 1: teams
        -- Master registry of canonical IPL franchise entities.
        -- Historical renames (e.g., Delhi Daredevils -> Delhi Capitals) are resolved
        -- to a single canonical team_id via the team_aliases table.
        -- =============================================================================
        CREATE TABLE teams (
            team_id SERIAL PRIMARY KEY,
            canonical_name VARCHAR(100) UNIQUE NOT NULL,
            short_code VARCHAR(10) UNIQUE NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        COMMENT ON TABLE teams IS 'Master registry of normalized IPL franchise entities.';
        COMMENT ON COLUMN teams.canonical_name IS 'Current canonical franchise name (e.g. Royal Challengers Bengaluru).';
        COMMENT ON COLUMN teams.short_code IS 'Standard 2-4 letter abbreviation (e.g. RCB, CSK, MI).';
        COMMENT ON COLUMN teams.is_active IS 'False for defunct franchises like Deccan Chargers or Gujarat Lions.';


        -- =============================================================================
        -- TABLE 2: team_aliases
        -- Resolves historical, rebranded, or alternate franchise names found in Cricsheet
        -- JSON files to their canonical teams record.
        -- =============================================================================
        CREATE TABLE team_aliases (
            alias_id SERIAL PRIMARY KEY,
            team_id INT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
            alias_name VARCHAR(100) UNIQUE NOT NULL
        );

        CREATE INDEX idx_team_aliases_name ON team_aliases (alias_name);

        COMMENT ON TABLE team_aliases IS 'Maps historical/rebranded names to canonical teams.';
        COMMENT ON COLUMN team_aliases.alias_name IS 'Exact franchise string in Cricsheet files (e.g. Kings XI Punjab).';


        -- =============================================================================
        -- TABLE 3: players
        -- Master registry for cricketers.
        -- Uses Cricsheet 8-character hex identifier as the primary identity key.
        --
        -- PLAYER IDENTITY & FALLBACK SPECIFICATION:
        -- 1. Official Cricsheet registry players use their verified hex ID (e.g. 'bbd41817').
        -- 2. If a match file lists a player lacking a registry ID, the ingestion service
        --    must NOT globally merge players based only on similar names.
        -- 3. Instead, it generates a deterministic, match-scoped fallback ID:
        --       'fallback:{match_id}:{team_id}:{sha256(normalized_name)[:32]}'
        --    Maximum length: 9 + 10 + 1 + 10 + 1 + 32 = 63 characters <= VARCHAR(64).
        --    and sets is_unresolved = TRUE.
        -- 4. Source match scorecard names are always preserved in match_players.match_display_name
        --    and deliveries.batter_name / bowler_name.
        -- 5. Unresolved players can be audited with: SELECT * FROM players WHERE is_unresolved = TRUE;
        -- =============================================================================
        CREATE TABLE players (
            player_id VARCHAR(64) PRIMARY KEY,
            canonical_name VARCHAR(150) NOT NULL,
            is_unresolved BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX idx_players_canonical_name ON players (canonical_name);

        COMMENT ON TABLE players IS 'Master registry of IPL players using Cricsheet unique registry IDs or match-scoped fallbacks.';
        COMMENT ON COLUMN players.player_id IS 'Cricsheet hex ID or match-scoped fallback (fallback:{match_id}:{team_id}:{sha256[:32]}).';
        COMMENT ON COLUMN players.is_unresolved IS 'TRUE if identity was generated by match-scoped fallback rather than verified Cricsheet registry key.';


        -- =============================================================================
        -- TABLE 4: matches
        -- Top-level match overview, outcomes, venues, and queryable source JSONB.
        -- Direct match participation is authoritatively handled by match_teams.
        --
        -- NOTE ON TOSS_WINNER_ID & WINNER_ID INTEGRITY:
        -- To avoid circular table-locking and chicken-and-egg dependency deadlocks
        -- with match_teams, these reference teams(team_id) directly. The Ingestion
        -- Validation Service strictly asserts that toss_winner_id and winner_id
        -- belong to the two match participants before committing the transaction.
        -- =============================================================================
        CREATE TABLE matches (
            match_id INT PRIMARY KEY,
            season VARCHAR(15) NOT NULL,
            match_number INT,
            stage VARCHAR(50),
            match_date DATE NOT NULL,
            end_date DATE,
            venue VARCHAR(200) NOT NULL,
            city VARCHAR(100),
            toss_winner_id INT REFERENCES teams(team_id) ON DELETE RESTRICT,
            toss_decision VARCHAR(10) CHECK (toss_decision IN ('bat', 'field')),
            winner_id INT REFERENCES teams(team_id) ON DELETE RESTRICT,
            result_type VARCHAR(30) NOT NULL CHECK (result_type IN ('runs', 'wickets', 'tie', 'no result', 'eliminator')),
            result_method VARCHAR(30),  
            win_by_runs INT CHECK (win_by_runs >= 0),
            win_by_wickets INT CHECK (win_by_wickets >= 0 AND win_by_wickets <= 10),
            cricsheet_revision INT NOT NULL DEFAULT 1,
            cricsheet_created_date DATE,
            raw_json JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX idx_matches_season ON matches (season);
        CREATE INDEX idx_matches_date ON matches (match_date);
        CREATE INDEX idx_matches_winner ON matches (winner_id);
        CREATE INDEX idx_matches_raw_json ON matches USING gin (raw_json);

        COMMENT ON TABLE matches IS 'Match-level results, conditions, and parsed JSONB document.';
        COMMENT ON COLUMN matches.season IS 'Supports span seasons (e.g. 2007/08, 2020/21, 2024).';
        COMMENT ON COLUMN matches.end_date IS 'Set when matches span reserve days (e.g. 2023 Final).';
        COMMENT ON COLUMN matches.toss_winner_id IS 'Toss winner; validated by ingestion service against match_teams.';
        COMMENT ON COLUMN matches.winner_id IS 'Match winner; validated by ingestion service against match_teams.';
        COMMENT ON COLUMN matches.raw_json IS 'Structured queryable JSONB for GIN indexing and Gemini RAG context.';
        COMMENT ON COLUMN matches.result_method IS  'Match result method, such as D/L. NULL when no special method is recorded.';


        -- =============================================================================
        -- TABLE 5: match_teams
        -- Authoritative match participation junction table.
        -- Links the participating franchises per match and preserves
        -- original match-day scorecard names.
        -- Enforces that at most slots 1 and 2 exist, and teams cannot play themselves.
        -- Ingestion service strictly asserts exactly 2 teams exist before commit.
        -- =============================================================================
        CREATE TABLE match_teams (
            match_team_id BIGSERIAL PRIMARY KEY,
            match_id INT NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
            team_id INT NOT NULL REFERENCES teams(team_id) ON DELETE RESTRICT,
            team_number SMALLINT NOT NULL CHECK (team_number IN (1, 2)),
            original_team_name VARCHAR(100) NOT NULL,
            CONSTRAINT uq_match_teams_match_number UNIQUE (match_id, team_number),
            CONSTRAINT uq_match_teams_match_team UNIQUE (match_id, team_id)
        );

        CREATE INDEX idx_match_teams_team ON match_teams (team_id);

        COMMENT ON TABLE match_teams IS 'Authoritative record of participating franchises in a match.';
        COMMENT ON COLUMN match_teams.team_number IS '1 or 2 as designated in the match scorecard.';
        COMMENT ON COLUMN match_teams.original_team_name IS 'Exact franchise name printed on that match day.';


        -- =============================================================================
        -- TABLE 6: match_players
        -- Playing squad / nominated players for each team in a match.
        -- Enforces that a player is assigned to a team participating in that match
        -- via a composite foreign key referencing match_teams(match_id, team_id).
        -- Exposes composite UNIQUE (match_id, player_id) for downstream tables.
        -- =============================================================================
        CREATE TABLE match_players (
            match_player_id BIGSERIAL PRIMARY KEY,
            match_id INT NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
            player_id VARCHAR(64) NOT NULL REFERENCES players(player_id) ON DELETE RESTRICT,
            team_id INT NOT NULL,
            match_display_name VARCHAR(150) NOT NULL,
            CONSTRAINT uq_match_players_match_player UNIQUE (match_id, player_id),
            CONSTRAINT fk_match_players_match_team FOREIGN KEY (match_id, team_id)
                REFERENCES match_teams(match_id, team_id) ON DELETE CASCADE
        );

        CREATE INDEX idx_match_players_match ON match_players (match_id);
        CREATE INDEX idx_match_players_player ON match_players (player_id);

        COMMENT ON TABLE match_players IS 'Match-day squads/playing XIs linked to match participants.';
        COMMENT ON COLUMN match_players.match_display_name IS 'Exact player name as recorded in the match scorecard.';


        -- =============================================================================
        -- TABLE 7: match_awards
        -- Match honors supporting single or joint recipients (e.g. Player of the Match).
        -- Composite foreign key guarantees award recipients are verified match participants.
        -- =============================================================================
        CREATE TABLE match_awards (
            award_id BIGSERIAL PRIMARY KEY,
            match_id INT NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
            award_name VARCHAR(100) NOT NULL DEFAULT 'Player of the Match',
            player_id VARCHAR(64) NOT NULL REFERENCES players(player_id) ON DELETE RESTRICT,
            recipient_name VARCHAR(150) NOT NULL,
            CONSTRAINT uq_match_awards_recipient UNIQUE (match_id, award_name, player_id),
            CONSTRAINT fk_match_awards_match_player FOREIGN KEY (match_id, player_id)
                REFERENCES match_players(match_id, player_id) ON DELETE CASCADE
        );

        CREATE INDEX idx_match_awards_player ON match_awards (player_id);

        COMMENT ON TABLE match_awards IS 'Player awards supporting joint recipients per match.';


        -- =============================================================================
        -- TABLE 8: innings
        -- Stores validated innings summaries and target chase parameters.
        -- Composite foreign keys guarantee batting and bowling teams are the
        -- verified match participants recorded in match_teams.
        -- Exposes composite UNIQUE (innings_id, match_id) for downstream deliveries.
        -- =============================================================================
        CREATE TABLE innings (
            innings_id BIGSERIAL PRIMARY KEY,
            match_id INT NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
            innings_number SMALLINT NOT NULL CHECK (innings_number >= 1),
            batting_team_id INT NOT NULL,
            bowling_team_id INT NOT NULL,
            is_super_over BOOLEAN NOT NULL DEFAULT FALSE,
            target_runs INT CHECK (target_runs >= 0),
            target_legal_balls INT CHECK (target_legal_balls >= 0),
            total_runs INT NOT NULL DEFAULT 0 CHECK (total_runs >= 0),
            total_wickets INT NOT NULL DEFAULT 0 CHECK (total_wickets >= 0 AND total_wickets <= 10),
            legal_balls_bowled INT NOT NULL DEFAULT 0 CHECK (legal_balls_bowled >= 0),
            powerplays JSONB,
            CONSTRAINT uq_innings_match_number UNIQUE (match_id, innings_number),
            CONSTRAINT uq_innings_id_match UNIQUE (innings_id, match_id),
            CONSTRAINT fk_innings_batting_team FOREIGN KEY (match_id, batting_team_id)
                REFERENCES match_teams(match_id, team_id) ON DELETE CASCADE,
            CONSTRAINT fk_innings_bowling_team FOREIGN KEY (match_id, bowling_team_id)
                REFERENCES match_teams(match_id, team_id) ON DELETE CASCADE,
            CONSTRAINT chk_innings_distinct_teams CHECK (batting_team_id <> bowling_team_id)
        );

        CREATE INDEX idx_innings_match_id ON innings (match_id);
        CREATE INDEX idx_innings_batting_team ON innings (batting_team_id);
        CREATE INDEX idx_innings_bowling_team ON innings (bowling_team_id);

        COMMENT ON TABLE innings IS 'Validated innings summaries and chase parameters.';
        COMMENT ON COLUMN innings.legal_balls_bowled IS 'Integer count of legal deliveries bowled (avoids decimal over errors).';
        COMMENT ON COLUMN innings.innings_number IS 'Sequential innings index (1, 2, 3.. accommodates multi-super overs).';


        -- =============================================================================
        -- TABLE 9: deliveries
        -- Granular ball-by-ball delivery engine.
        -- Linked to innings and matches via composite FK (innings_id, match_id).
        -- Batter, bowler, and non-striker are strictly linked to match_players(match_id, player_id).
        -- Over number is 0-indexed (0 to N).
        -- CHECK constraints enforce total_runs and extras component summation.
        -- Exposes composite UNIQUE (delivery_id, match_id) for downstream wickets.
        -- =============================================================================
        CREATE TABLE deliveries (
            delivery_id BIGSERIAL PRIMARY KEY,
            innings_id BIGINT NOT NULL,
            match_id INT NOT NULL,
            over_number SMALLINT NOT NULL CHECK (over_number >= 0),
            delivery_sequence SMALLINT NOT NULL CHECK (delivery_sequence >= 1),
            batter_id VARCHAR(64) NOT NULL REFERENCES players(player_id) ON DELETE RESTRICT,
            batter_name VARCHAR(150) NOT NULL,
            bowler_id VARCHAR(64) NOT NULL REFERENCES players(player_id) ON DELETE RESTRICT,
            bowler_name VARCHAR(150) NOT NULL,
            non_striker_id VARCHAR(64) NOT NULL REFERENCES players(player_id) ON DELETE RESTRICT,
            non_striker_name VARCHAR(150) NOT NULL,
            batter_runs SMALLINT NOT NULL DEFAULT 0 CHECK (batter_runs >= 0),
            extra_runs SMALLINT NOT NULL DEFAULT 0 CHECK (extra_runs >= 0),
            total_runs SMALLINT NOT NULL DEFAULT 0 CHECK (total_runs >= 0),
            wide_runs SMALLINT NOT NULL DEFAULT 0 CHECK (wide_runs >= 0),
            no_ball_runs SMALLINT NOT NULL DEFAULT 0 CHECK (no_ball_runs >= 0),
            leg_bye_runs SMALLINT NOT NULL DEFAULT 0 CHECK (leg_bye_runs >= 0),
            bye_runs SMALLINT NOT NULL DEFAULT 0 CHECK (bye_runs >= 0),
            penalty_runs SMALLINT NOT NULL DEFAULT 0 CHECK (penalty_runs >= 0),
            is_legal_ball BOOLEAN GENERATED ALWAYS AS (wide_runs = 0 AND no_ball_runs = 0) STORED,
            review JSONB,
            CONSTRAINT uq_deliveries_over_sequence UNIQUE (innings_id, over_number, delivery_sequence),
            CONSTRAINT uq_deliveries_delivery_match UNIQUE (delivery_id, match_id),
            CONSTRAINT fk_deliveries_innings_match FOREIGN KEY (innings_id, match_id)
                REFERENCES innings(innings_id, match_id) ON DELETE CASCADE,
            CONSTRAINT fk_deliveries_batter_match FOREIGN KEY (match_id, batter_id)
                REFERENCES match_players(match_id, player_id) ON DELETE RESTRICT,
            CONSTRAINT fk_deliveries_bowler_match FOREIGN KEY (match_id, bowler_id)
                REFERENCES match_players(match_id, player_id) ON DELETE RESTRICT,
            CONSTRAINT fk_deliveries_non_striker_match FOREIGN KEY (match_id, non_striker_id)
                REFERENCES match_players(match_id, player_id) ON DELETE RESTRICT,
            CONSTRAINT chk_deliveries_total_runs CHECK (total_runs = batter_runs + extra_runs),
            CONSTRAINT chk_deliveries_extras_sum CHECK (extra_runs = wide_runs + no_ball_runs + leg_bye_runs + bye_runs + penalty_runs)
        );

        CREATE INDEX idx_deliveries_batter ON deliveries (batter_id);
        CREATE INDEX idx_deliveries_bowler ON deliveries (bowler_id);
        CREATE INDEX idx_deliveries_match_innings ON deliveries (match_id, innings_id);
        CREATE INDEX idx_deliveries_legal_bowler ON deliveries (bowler_id) WHERE is_legal_ball = TRUE;
        CREATE INDEX idx_deliveries_match_batter ON deliveries (match_id, batter_id);
        CREATE INDEX idx_deliveries_match_bowler ON deliveries (match_id, bowler_id);
        CREATE INDEX idx_deliveries_match_non_striker ON deliveries (match_id, non_striker_id);

        COMMENT ON TABLE deliveries IS 'Ball-by-ball delivery records for statistical calculation.';
        COMMENT ON COLUMN deliveries.over_number IS '0-indexed over number (0 represents 1st over, 19 represents 20th over).';
        COMMENT ON COLUMN deliveries.delivery_sequence IS '1-based sequential delivery index within the over.';
        COMMENT ON COLUMN deliveries.is_legal_ball IS 'Computed: TRUE iff delivery is neither a wide nor a no-ball.';
        COMMENT ON COLUMN deliveries.penalty_runs IS 'Penalty extras (never charged against the individual bowler).';


        -- =============================================================================
        -- TABLE 10: delivery_wickets
        -- Decoupled table recording every dismissal occurring on a delivery.
        -- Linked to deliveries via composite FK (delivery_id, match_id).
        -- Dismissed player is strictly linked to match_players(match_id, player_id).
        -- =============================================================================
        CREATE TABLE delivery_wickets (
            wicket_id BIGSERIAL PRIMARY KEY,
            delivery_id BIGINT NOT NULL,
            match_id INT NOT NULL,
            dismissal_kind VARCHAR(50) NOT NULL,
            player_dismissed_id VARCHAR(64) NOT NULL REFERENCES players(player_id) ON DELETE RESTRICT,
            player_dismissed_name VARCHAR(150) NOT NULL,
            is_bowler_credit BOOLEAN NOT NULL,
            fielders JSONB,
            CONSTRAINT fk_delivery_wickets_delivery_match FOREIGN KEY (delivery_id, match_id)
                REFERENCES deliveries(delivery_id, match_id) ON DELETE CASCADE,
            CONSTRAINT fk_delivery_wickets_dismissed_match FOREIGN KEY (match_id, player_dismissed_id)
                REFERENCES match_players(match_id, player_id) ON DELETE RESTRICT
        );

        CREATE INDEX idx_delivery_wickets_delivery ON delivery_wickets (delivery_id);
        CREATE INDEX idx_delivery_wickets_dismissed ON delivery_wickets (player_dismissed_id);
        CREATE INDEX idx_delivery_wickets_bowler ON delivery_wickets (is_bowler_credit) WHERE is_bowler_credit = TRUE;
        CREATE INDEX idx_delivery_wickets_match_dismissed ON delivery_wickets (match_id, player_dismissed_id);

        COMMENT ON TABLE delivery_wickets IS 'Decoupled dismissal records supporting multi-wicket deliveries.';
        COMMENT ON COLUMN delivery_wickets.is_bowler_credit IS 'TRUE for bowled, caught, caught and bowled, lbw, stumped and hit wicket. FALSE for run out, retired hurt, retired out and obstructing the field.';
        COMMENT ON COLUMN delivery_wickets.fielders IS 'JSONB array of fielders involved in catches, stumpings, and run outs.';


        -- =============================================================================
        -- TABLE 11: sync_files
        -- Tracks file synchronization state and cryptographic content hashes.
        -- Standalone tracking record: not cascade-deleted during match replacements.
        -- =============================================================================
        CREATE TABLE sync_files (
            match_id INT PRIMARY KEY,
            file_name VARCHAR(100) NOT NULL,
            file_sha256 VARCHAR(64) NOT NULL,
            cricsheet_revision INT NOT NULL DEFAULT 1,
            status VARCHAR(30) NOT NULL DEFAULT 'synced' CHECK (status IN ('synced', 'updated', 'failed')),
            raw_archive_url TEXT,
            last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX idx_sync_files_sha256 ON sync_files (file_sha256);

        COMMENT ON TABLE sync_files IS 'File-level synchronization status and SHA-256 change detection metadata.';
        COMMENT ON COLUMN sync_files.file_sha256 IS 'SHA-256 hash of Cricsheet JSON payload for change detection.';


        -- =============================================================================
        -- TABLE 12: sync_history
        -- Append-only audit log for periodic 6-hour cron and manual sync runs.
        -- Historical records are never modified or deleted by match replacements.
        -- =============================================================================
        CREATE TABLE sync_history (
            sync_id BIGSERIAL PRIMARY KEY,
            triggered_by VARCHAR(50) NOT NULL CHECK (triggered_by IN ('cron', 'manual', 'initial_import')),
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            status VARCHAR(30) NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'partial_failure', 'failed')),
            files_checked INT NOT NULL DEFAULT 0,
            files_downloaded INT NOT NULL DEFAULT 0,
            matches_inserted INT NOT NULL DEFAULT 0,
            matches_updated INT NOT NULL DEFAULT 0,
            matches_skipped INT NOT NULL DEFAULT 0,
            matches_failed INT NOT NULL DEFAULT 0,
            error_details JSONB
        );

        CREATE INDEX idx_sync_history_started ON sync_history (started_at DESC);

        COMMENT ON TABLE sync_history IS 'Append-only audit ledger tracking every synchronization job execution.';
