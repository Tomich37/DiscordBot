from app.modules.alchemy_connect import (
    AlchemyElement,
    AlchemyGuildDiscovery,
    AlchemyPlayer,
    AlchemyPlayerElement,
    AlchemyRecipe,
    AlchemyTransaction,
    ContestMessage,
    ContestRun,
    Contests,
    Giveaway,
    GiveawayParticipant,
    GiveawayWin,
    GuildUserStats,
    MessageStatistics,
    MusicPlaylist,
    MusicPlaylistTrack,
    RecruitmentPosition,
    RecruitmentQuestion,
    Recruitments,
    Session,
    TrackedAnonimusChannel,
    TrackedChannel,
    engine,
)
from datetime import date, datetime


class Database:
    MUSIC_PENDING_STATUSES = ("pending",)
    GLOBAL_ALCHEMY_GUILD_ID = 0

    def _get_alchemy_player(self, db, guild_id: int, user_id: int):
        return db.query(AlchemyPlayer).filter_by(guild_id=guild_id, user_id=user_id).first()

    def _get_global_alchemy_element(self, db, normalized_name: str):
        return (
            db.query(AlchemyElement)
            .filter_by(guild_id=self.GLOBAL_ALCHEMY_GUILD_ID, normalized_name=normalized_name)
            .first()
        )

    def _get_or_create_alchemy_element(
        self,
        db,
        normalized_name: str,
        display_name: str,
        first_discoverer_id: int | None = None,
    ):
        element = self._get_global_alchemy_element(db, normalized_name)
        if element:
            return element, False

        element = AlchemyElement(
            guild_id=self.GLOBAL_ALCHEMY_GUILD_ID,
            normalized_name=normalized_name,
            display_name=display_name,
            first_discoverer_id=first_discoverer_id,
        )
        db.add(element)
        db.flush()
        return element, True

    def _add_alchemy_player_element(self, db, player_id: int, element_id: int) -> bool:
        existing_element = (
            db.query(AlchemyPlayerElement)
            .filter_by(player_id=player_id, element_id=element_id)
            .first()
        )
        if existing_element:
            return False

        db.add(AlchemyPlayerElement(player_id=player_id, element_id=element_id))
        db.flush()
        return True

    def _add_alchemy_transaction(self, db, player: AlchemyPlayer, amount: int, reason: str):
        db.add(
            AlchemyTransaction(
                player_id=player.id,
                amount=amount,
                reason=reason,
                balance_after=player.balance,
            )
        )

    def _ensure_base_alchemy_elements(self, db, player: AlchemyPlayer, base_elements: list[tuple[str, str]]) -> int:
        added_count = 0
        for normalized_name, display_name in base_elements:
            element, _ = self._get_or_create_alchemy_element(
                db,
                normalized_name,
                display_name,
            )
            if self._add_alchemy_player_element(db, player.id, element.id):
                added_count += 1
        return added_count

    def start_alchemy_player(
        self,
        guild_id: int,
        user_id: int,
        start_balance: int,
        base_elements: list[tuple[str, str]],
    ) -> dict:
        with Session(autoflush=False, bind=engine) as db:
            player = self._get_alchemy_player(db, guild_id, user_id)
            if player:
                existing_element_count = db.query(AlchemyPlayerElement).filter_by(player_id=player.id).count()
                added_count = self._ensure_base_alchemy_elements(db, player, base_elements)
                if added_count:
                    if existing_element_count == 0 and start_balance > 0:
                        player.balance += start_balance
                        self._add_alchemy_transaction(db, player, start_balance, "alchemy_start")
                    player.updated_at = datetime.utcnow()
                    db.commit()

                return {
                    "created": bool(added_count),
                    "balance": player.balance,
                    "first_discovery_count": player.first_discovery_count,
                    "element_count": existing_element_count + added_count,
                }

            now = datetime.utcnow()
            player = AlchemyPlayer(
                guild_id=guild_id,
                user_id=user_id,
                balance=start_balance,
                created_at=now,
                updated_at=now,
            )
            db.add(player)
            db.flush()
            self._add_alchemy_transaction(db, player, start_balance, "start")

            self._ensure_base_alchemy_elements(db, player, base_elements)

            db.commit()
            return {
                "created": True,
                "balance": player.balance,
                "first_discovery_count": player.first_discovery_count,
                "element_count": len(base_elements),
            }

    def claim_daily_reward(self, guild_id: int, user_id: int, reward: int, today: date) -> dict:
        with Session(autoflush=False, bind=engine) as db:
            player = self._get_alchemy_player(db, guild_id, user_id)
            if not player:
                now = datetime.utcnow()
                player = AlchemyPlayer(
                    guild_id=guild_id,
                    user_id=user_id,
                    balance=0,
                    created_at=now,
                    updated_at=now,
                )
                db.add(player)
                db.flush()

            if player.last_daily_at == today:
                return {
                    "status": "already_claimed",
                    "balance": player.balance,
                    "last_daily_at": player.last_daily_at,
                }

            player.balance += reward
            player.last_daily_at = today
            player.updated_at = datetime.utcnow()
            self._add_alchemy_transaction(db, player, reward, "daily")
            db.commit()
            return {
                "status": "claimed",
                "balance": player.balance,
                "reward": reward,
                "last_daily_at": player.last_daily_at,
            }

    def get_alchemy_profile(self, guild_id: int, user_id: int) -> dict:
        with Session(autoflush=False, bind=engine) as db:
            player = self._get_alchemy_player(db, guild_id, user_id)
            if not player:
                return {
                    "exists": False,
                    "balance": 0,
                    "first_discovery_count": 0,
                    "element_count": 0,
                    "last_daily_at": None,
                }

            element_count = (
                db.query(AlchemyPlayerElement)
                .filter_by(player_id=player.id)
                .count()
            )
            return {
                "exists": True,
                "balance": player.balance,
                "first_discovery_count": player.first_discovery_count,
                "element_count": element_count,
                "last_daily_at": player.last_daily_at,
            }

    def get_alchemy_inventory_count(self, guild_id: int, user_id: int) -> int:
        with Session(autoflush=False, bind=engine) as db:
            player = self._get_alchemy_player(db, guild_id, user_id)
            if not player:
                return 0

            return db.query(AlchemyPlayerElement).filter_by(player_id=player.id).count()

    def has_alchemy_elements(self, guild_id: int, user_id: int, element_names: list[str]) -> dict:
        with Session(autoflush=False, bind=engine) as db:
            player = self._get_alchemy_player(db, guild_id, user_id)
            if not player:
                return {"status": "not_started", "missing": element_names}

            if not db.query(AlchemyPlayerElement).filter_by(player_id=player.id).first():
                return {"status": "not_started", "missing": element_names}

            owned_rows = (
                db.query(AlchemyElement.normalized_name)
                .join(AlchemyPlayerElement, AlchemyPlayerElement.element_id == AlchemyElement.id)
                .filter(
                    AlchemyPlayerElement.player_id == player.id,
                    AlchemyElement.guild_id == self.GLOBAL_ALCHEMY_GUILD_ID,
                    AlchemyElement.normalized_name.in_(element_names),
                )
                .all()
            )
            owned_names = {row[0] for row in owned_rows}
            missing = [element_name for element_name in element_names if element_name not in owned_names]
            return {"status": "ok", "missing": missing}

    def get_related_alchemy_element_names(self, element_names: list[str], max_depth: int = 5) -> tuple[str, ...]:
        with Session(autoflush=False, bind=engine) as db:
            forbidden_names = []
            visited_names = set()
            queue = [(element_name, 0) for element_name in element_names]

            while queue:
                element_name, depth = queue.pop(0)
                if element_name in visited_names:
                    continue

                visited_names.add(element_name)
                forbidden_names.append(element_name)

                if depth >= max_depth:
                    continue

                parent_recipes = (
                    db.query(AlchemyRecipe.left_element, AlchemyRecipe.right_element)
                    .join(AlchemyElement, AlchemyElement.id == AlchemyRecipe.result_element_id)
                    .filter(
                        AlchemyRecipe.guild_id == self.GLOBAL_ALCHEMY_GUILD_ID,
                        AlchemyElement.guild_id == self.GLOBAL_ALCHEMY_GUILD_ID,
                        AlchemyElement.normalized_name == element_name,
                    )
                    .all()
                )

                # Поднимаемся по цепочке происхождения элемента до заданной глубины.
                for left_element, right_element in parent_recipes:
                    if left_element not in visited_names:
                        queue.append((left_element, depth + 1))
                    if right_element not in visited_names:
                        queue.append((right_element, depth + 1))

            return tuple(forbidden_names)

    def get_known_alchemy_element_names(self) -> tuple[str, ...]:
        with Session(autoflush=False, bind=engine) as db:
            rows = (
                db.query(AlchemyElement.normalized_name)
                .filter_by(guild_id=self.GLOBAL_ALCHEMY_GUILD_ID)
                .all()
            )
            return tuple(row[0] for row in rows)

    def claim_alchemy_daily(self, guild_id: int, user_id: int, reward: int, today: date) -> dict:
        with Session(autoflush=False, bind=engine) as db:
            player = self._get_alchemy_player(db, guild_id, user_id)
            if not player:
                return {"status": "not_started"}
            if player.last_daily_at == today:
                return {
                    "status": "already_claimed",
                    "balance": player.balance,
                    "last_daily_at": player.last_daily_at,
                }

            player.balance += reward
            player.last_daily_at = today
            player.updated_at = datetime.utcnow()
            self._add_alchemy_transaction(db, player, reward, "daily")
            db.commit()
            return {
                "status": "claimed",
                "balance": player.balance,
                "reward": reward,
                "last_daily_at": player.last_daily_at,
            }

    def spend_alchemy_currency(self, guild_id: int, user_id: int, amount: int, reason: str = "combine") -> dict:
        with Session(autoflush=False, bind=engine) as db:
            player = self._get_alchemy_player(db, guild_id, user_id)
            if not player:
                return {"status": "not_started"}
            if player.balance < amount:
                return {"status": "not_enough", "balance": player.balance}

            player.balance -= amount
            player.updated_at = datetime.utcnow()
            self._add_alchemy_transaction(db, player, -amount, reason)
            db.commit()
            return {"status": "spent", "balance": player.balance}

    def refund_alchemy_currency(self, guild_id: int, user_id: int, amount: int, reason: str = "refund") -> dict:
        with Session(autoflush=False, bind=engine) as db:
            player = self._get_alchemy_player(db, guild_id, user_id)
            if not player:
                return {"status": "not_started"}

            player.balance += amount
            player.updated_at = datetime.utcnow()
            self._add_alchemy_transaction(db, player, amount, reason)
            db.commit()
            return {"status": "refunded", "balance": player.balance}

    def get_alchemy_recipe(self, guild_id: int, left_element: str, right_element: str) -> dict | None:
        with Session(autoflush=False, bind=engine) as db:
            recipe = (
                db.query(AlchemyRecipe)
                .filter_by(
                    guild_id=self.GLOBAL_ALCHEMY_GUILD_ID,
                    left_element=left_element,
                    right_element=right_element,
                )
                .first()
            )
            if not recipe:
                return None

            result = db.query(AlchemyElement).filter_by(id=recipe.result_element_id).first()
            if not result:
                return None

            guild_discovery = (
                db.query(AlchemyGuildDiscovery)
                .filter_by(guild_id=guild_id, recipe_id=recipe.id)
                .first()
            )
            return {
                "id": recipe.id,
                "result_normalized": result.normalized_name,
                "result_display": result.display_name,
                "global_first_discoverer_id": recipe.first_discoverer_id,
                "guild_first_discoverer_id": (
                    guild_discovery.first_discoverer_id if guild_discovery else None
                ),
                "is_discovered_on_guild": bool(guild_discovery),
                "created_at": recipe.created_at,
            }

    def get_discovered_alchemy_recipes_page(self, guild_id: int, page: int, page_size: int) -> dict:
        with Session(autoflush=False, bind=engine) as db:
            base_query = (
                db.query(AlchemyGuildDiscovery)
                .filter_by(guild_id=guild_id)
            )
            total_count = base_query.count()
            total_pages = max((total_count + page_size - 1) // page_size, 1)
            page = min(max(page, 0), total_pages - 1)

            discoveries = (
                base_query
                .order_by(AlchemyGuildDiscovery.discovered_at.desc())
                .offset(page * page_size)
                .limit(page_size)
                .all()
            )

            items = []
            for discovery in discoveries:
                recipe = db.query(AlchemyRecipe).filter_by(id=discovery.recipe_id).first()
                if not recipe:
                    continue

                result = db.query(AlchemyElement).filter_by(id=recipe.result_element_id).first()
                if not result:
                    continue

                items.append(
                    {
                        "left_element": recipe.left_element,
                        "right_element": recipe.right_element,
                        "result_display": result.display_name,
                        "first_discoverer_id": discovery.first_discoverer_id,
                        "discovered_at": discovery.discovered_at,
                    }
                )

            return {
                "items": items,
                "page": page,
                "total_pages": total_pages,
                "total_count": total_count,
            }

    def learn_known_alchemy_recipe(self, guild_id: int, user_id: int, result_normalized: str) -> dict:
        with Session(autoflush=False, bind=engine) as db:
            player = self._get_alchemy_player(db, guild_id, user_id)
            if not player:
                return {"status": "not_started"}

            element = (
                db.query(AlchemyElement)
                .filter_by(
                    guild_id=self.GLOBAL_ALCHEMY_GUILD_ID,
                    normalized_name=result_normalized,
                )
                .first()
            )
            if not element:
                return {"status": "missing_element"}

            added = self._add_alchemy_player_element(db, player.id, element.id)
            db.commit()
            return {
                "status": "learned",
                "added_to_inventory": added,
                "result_display": element.display_name,
            }

    def discover_known_alchemy_recipe_on_guild(
        self,
        guild_id: int,
        user_id: int,
        recipe_id: int,
    ) -> dict:
        with Session(autoflush=False, bind=engine) as db:
            player = self._get_alchemy_player(db, guild_id, user_id)
            if not player:
                return {"status": "not_started"}

            recipe = db.query(AlchemyRecipe).filter_by(id=recipe_id).first()
            if not recipe:
                return {"status": "missing_recipe"}

            result = db.query(AlchemyElement).filter_by(id=recipe.result_element_id).first()
            if not result:
                return {"status": "missing_element"}

            discovery = (
                db.query(AlchemyGuildDiscovery)
                .filter_by(guild_id=guild_id, recipe_id=recipe.id)
                .first()
            )
            added = self._add_alchemy_player_element(db, player.id, result.id)
            if discovery:
                db.commit()
                return {
                    "status": "already_discovered_on_guild",
                    "result_display": result.display_name,
                    "result_normalized": result.normalized_name,
                    "added_to_inventory": added,
                    "guild_first_discoverer_id": discovery.first_discoverer_id,
                }

            db.add(
                AlchemyGuildDiscovery(
                    guild_id=guild_id,
                    recipe_id=recipe.id,
                    first_discoverer_id=user_id,
                )
            )
            player.first_discovery_count += 1
            player.updated_at = datetime.utcnow()
            db.commit()
            return {
                "status": "discovered_on_guild",
                "result_display": result.display_name,
                "result_normalized": result.normalized_name,
                "added_to_inventory": added,
                "first_discovery_count": player.first_discovery_count,
            }

    def create_alchemy_discovery(
        self,
        guild_id: int,
        user_id: int,
        left_element: str,
        right_element: str,
        result_normalized: str,
        result_display: str,
        openai_response_id: str | None = None,
    ) -> dict:
        with Session(autoflush=False, bind=engine) as db:
            player = self._get_alchemy_player(db, guild_id, user_id)
            if not player:
                return {"status": "not_started"}

            existing_recipe = (
                db.query(AlchemyRecipe)
                .filter_by(
                    guild_id=self.GLOBAL_ALCHEMY_GUILD_ID,
                    left_element=left_element,
                    right_element=right_element,
                )
                .first()
            )
            if existing_recipe:
                result = db.query(AlchemyElement).filter_by(id=existing_recipe.result_element_id).first()
                added = self._add_alchemy_player_element(db, player.id, result.id)
                discovery = (
                    db.query(AlchemyGuildDiscovery)
                    .filter_by(guild_id=guild_id, recipe_id=existing_recipe.id)
                    .first()
                )
                if not discovery:
                    db.add(
                        AlchemyGuildDiscovery(
                            guild_id=guild_id,
                            recipe_id=existing_recipe.id,
                            first_discoverer_id=user_id,
                        )
                    )
                    player.first_discovery_count += 1
                    player.updated_at = datetime.utcnow()
                    db.commit()
                    return {
                        "status": "discovered_on_guild",
                        "result_display": result.display_name,
                        "result_normalized": result.normalized_name,
                        "added_to_inventory": added,
                        "first_discovery_count": player.first_discovery_count,
                    }

                db.commit()
                return {
                    "status": "already_discovered_on_guild",
                    "result_display": result.display_name,
                    "result_normalized": result.normalized_name,
                    "added_to_inventory": added,
                }

            element, created_element = self._get_or_create_alchemy_element(
                db,
                result_normalized,
                result_display,
                first_discoverer_id=user_id,
            )
            recipe = AlchemyRecipe(
                guild_id=self.GLOBAL_ALCHEMY_GUILD_ID,
                left_element=left_element,
                right_element=right_element,
                result_element_id=element.id,
                first_discoverer_id=user_id,
                openai_response_id=openai_response_id,
            )
            db.add(recipe)
            db.flush()
            db.add(
                AlchemyGuildDiscovery(
                    guild_id=guild_id,
                    recipe_id=recipe.id,
                    first_discoverer_id=user_id,
                )
            )
            self._add_alchemy_player_element(db, player.id, element.id)
            player.first_discovery_count += 1
            player.updated_at = datetime.utcnow()

            db.commit()
            return {
                "status": "created",
                "result_display": element.display_name,
                "result_normalized": element.normalized_name,
                "created_element": created_element,
                "first_discovery_count": player.first_discovery_count,
            }

    def get_alchemy_inventory_page(self, guild_id: int, user_id: int, page: int, page_size: int) -> dict:
        with Session(autoflush=False, bind=engine) as db:
            player = self._get_alchemy_player(db, guild_id, user_id)
            if not player:
                return {"status": "not_started", "items": [], "page": 0, "total_pages": 1, "total_count": 0}

            if not db.query(AlchemyPlayerElement).filter_by(player_id=player.id).first():
                return {"status": "not_started", "items": [], "page": 0, "total_pages": 1, "total_count": 0}

            base_query = (
                db.query(AlchemyElement.display_name)
                .join(AlchemyPlayerElement, AlchemyPlayerElement.element_id == AlchemyElement.id)
                .filter(
                    AlchemyPlayerElement.player_id == player.id,
                    AlchemyElement.guild_id == self.GLOBAL_ALCHEMY_GUILD_ID,
                )
            )
            total_count = base_query.count()
            total_pages = max((total_count + page_size - 1) // page_size, 1)
            page = min(max(page, 0), total_pages - 1)
            rows = (
                base_query
                .order_by(AlchemyElement.display_name.asc())
                .offset(page * page_size)
                .limit(page_size)
                .all()
            )
            return {
                "status": "ok",
                "items": [row[0] for row in rows],
                "page": page,
                "total_pages": total_pages,
                "total_count": total_count,
            }

    def get_alchemy_top(self, guild_id: int, limit: int = 10) -> list[dict]:
        with Session(autoflush=False, bind=engine) as db:
            players = (
                db.query(AlchemyPlayer)
                .filter_by(guild_id=guild_id)
                .order_by(AlchemyPlayer.first_discovery_count.desc(), AlchemyPlayer.balance.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "user_id": player.user_id,
                    "balance": player.balance,
                    "first_discovery_count": player.first_discovery_count,
                    "element_count": db.query(AlchemyPlayerElement).filter_by(player_id=player.id).count(),
                }
                for player in players
                if player.first_discovery_count > 0 or player.balance > 0
            ]

    def _get_or_create_user_stats(self, db, guild_id: int, user_id: int):
        stats = db.query(GuildUserStats).filter_by(guild_id=guild_id, user_id=user_id).first()
        if stats:
            return stats

        now = datetime.utcnow()
        stats = GuildUserStats(guild_id=guild_id, user_id=user_id, stats_started_at=now, updated_at=now)
        db.add(stats)
        db.flush()
        return stats

    def increment_user_message_count(self, guild_id: int, user_id: int):
        with Session(autoflush=False, bind=engine) as db:
            stats = self._get_or_create_user_stats(db, guild_id, user_id)
            stats.message_count += 1
            stats.last_message_at = datetime.utcnow()
            stats.updated_at = datetime.utcnow()
            db.commit()

    def bulk_increment_user_message_counts(self, counters: dict[tuple[int, int], int]):
        if not counters:
            return

        with Session(autoflush=False, bind=engine) as db:
            now = datetime.utcnow()
            for (guild_id, user_id), message_count in counters.items():
                if message_count <= 0:
                    continue

                stats = self._get_or_create_user_stats(db, guild_id, user_id)
                stats.message_count += message_count
                stats.last_message_at = now
                stats.updated_at = now

            db.commit()

    def start_user_voice_session(self, guild_id: int, user_id: int, channel_id: int):
        with Session(autoflush=False, bind=engine) as db:
            stats = self._get_or_create_user_stats(db, guild_id, user_id)
            if not stats.voice_joined_at:
                stats.voice_joined_at = datetime.utcnow()
            stats.current_voice_channel_id = channel_id
            stats.updated_at = datetime.utcnow()
            db.commit()

    def finish_user_voice_session(self, guild_id: int, user_id: int):
        with Session(autoflush=False, bind=engine) as db:
            stats = db.query(GuildUserStats).filter_by(guild_id=guild_id, user_id=user_id).first()
            if not stats or not stats.voice_joined_at:
                return

            now = datetime.utcnow()
            voice_seconds = int((now - stats.voice_joined_at).total_seconds())
            if voice_seconds > 0:
                stats.total_voice_seconds += voice_seconds

            stats.current_voice_channel_id = None
            stats.voice_joined_at = None
            stats.updated_at = now
            db.commit()

    def reset_open_voice_sessions(self, guild_id: int):
        with Session(autoflush=False, bind=engine) as db:
            now = datetime.utcnow()
            open_sessions = (
                db.query(GuildUserStats)
                .filter(
                    GuildUserStats.guild_id == guild_id,
                    GuildUserStats.voice_joined_at.isnot(None),
                )
                .all()
            )

            for stats in open_sessions:
                stats.current_voice_channel_id = None
                stats.voice_joined_at = None
                stats.updated_at = now

            db.commit()

    def get_user_stats(self, guild_id: int, user_id: int) -> dict:
        with Session(autoflush=False, bind=engine) as db:
            stats = db.query(GuildUserStats).filter_by(guild_id=guild_id, user_id=user_id).first()
            if not stats:
                return {
                    "message_count": 0,
                    "total_voice_seconds": 0,
                    "stats_started_at": None,
                    "current_voice_channel_id": None,
                    "voice_joined_at": None,
                    "last_message_at": None,
                }

            return {
                "message_count": stats.message_count,
                "total_voice_seconds": stats.total_voice_seconds,
                "stats_started_at": stats.stats_started_at,
                "current_voice_channel_id": stats.current_voice_channel_id,
                "voice_joined_at": stats.voice_joined_at,
                "last_message_at": stats.last_message_at,
            }

    def get_guild_user_stats(self, guild_id: int) -> list[dict]:
        with Session(autoflush=False, bind=engine) as db:
            stats_rows = db.query(GuildUserStats).filter_by(guild_id=guild_id).all()
            return [
                {
                    "user_id": stats.user_id,
                    "message_count": stats.message_count,
                    "total_voice_seconds": stats.total_voice_seconds,
                    "stats_started_at": stats.stats_started_at,
                    "current_voice_channel_id": stats.current_voice_channel_id,
                    "voice_joined_at": stats.voice_joined_at,
                    "last_message_at": stats.last_message_at,
                }
                for stats in stats_rows
            ]

    def get_or_create_music_playlist(self, guild_id: int, user_id: int) -> int:
        with Session(autoflush=False, bind=engine) as db:
            playlist = (
                db.query(MusicPlaylist)
                .filter_by(guild_id=guild_id, user_id=user_id, is_active=True)
                .first()
            )
            if playlist:
                return playlist.id

            playlist = MusicPlaylist(guild_id=guild_id, user_id=user_id)
            db.add(playlist)
            db.commit()
            db.refresh(playlist)
            return playlist.id

    def append_music_tracks(self, guild_id: int, user_id: int, tracks: list[dict]) -> dict:
        if not tracks:
            return {"playlist_id": self.get_or_create_music_playlist(guild_id, user_id), "added_count": 0}

        with Session(autoflush=False, bind=engine) as db:
            now = datetime.utcnow()
            playlist = (
                db.query(MusicPlaylist)
                .filter_by(guild_id=guild_id, user_id=user_id, is_active=True)
                .first()
            )
            if not playlist:
                playlist = MusicPlaylist(guild_id=guild_id, user_id=user_id, created_at=now, updated_at=now)
                db.add(playlist)
                db.flush()

            last_position = (
                db.query(MusicPlaylistTrack.position)
                .filter_by(playlist_id=playlist.id)
                .order_by(MusicPlaylistTrack.position.desc())
                .first()
            )
            next_position = (last_position[0] + 1) if last_position else 1

            for offset, track in enumerate(tracks):
                db.add(
                    MusicPlaylistTrack(
                        playlist_id=playlist.id,
                        position=next_position + offset,
                        title=track["title"],
                        webpage_url=track["webpage_url"],
                        duration=track.get("duration"),
                        status="pending",
                        created_at=now,
                        updated_at=now,
                    )
                )

            playlist.updated_at = now
            db.commit()
            return {
                "playlist_id": playlist.id,
                "added_count": len(tracks),
                "first_position": next_position,
            }

    def get_next_music_track(self, guild_id: int, user_id: int) -> dict | None:
        with Session(autoflush=False, bind=engine) as db:
            playlist = (
                db.query(MusicPlaylist)
                .filter_by(guild_id=guild_id, user_id=user_id, is_active=True)
                .first()
            )
            if not playlist:
                return None

            track = (
                db.query(MusicPlaylistTrack)
                .filter(
                    MusicPlaylistTrack.playlist_id == playlist.id,
                    MusicPlaylistTrack.status.in_(self.MUSIC_PENDING_STATUSES),
                )
                .order_by(MusicPlaylistTrack.position.asc())
                .first()
            )
            if not track:
                return None

            return {
                "id": track.id,
                "playlist_id": playlist.id,
                "user_id": playlist.user_id,
                "position": track.position,
                "title": track.title,
                "webpage_url": track.webpage_url,
                "duration": track.duration,
                "status": track.status,
            }

    def get_music_playlist_page(self, guild_id: int, user_id: int, page: int, page_size: int) -> dict:
        with Session(autoflush=False, bind=engine) as db:
            playlist = (
                db.query(MusicPlaylist)
                .filter_by(guild_id=guild_id, user_id=user_id, is_active=True)
                .first()
            )
            if not playlist:
                return {"tracks": [], "total_count": 0, "total_pages": 1, "page": 0}

            base_query = (
                db.query(MusicPlaylistTrack)
                .filter(
                    MusicPlaylistTrack.playlist_id == playlist.id,
                    MusicPlaylistTrack.status == "pending",
                )
            )
            total_count = base_query.count()
            total_pages = max((total_count + page_size - 1) // page_size, 1)
            page = min(max(page, 0), total_pages - 1)

            tracks = (
                base_query
                .order_by(MusicPlaylistTrack.position.asc())
                .offset(page * page_size)
                .limit(page_size)
                .all()
            )
            return {
                "tracks": [
                    {
                        "id": track.id,
                        "position": track.position,
                        "title": track.title,
                        "webpage_url": track.webpage_url,
                        "duration": track.duration,
                        "status": track.status,
                    }
                    for track in tracks
                ],
                "total_count": total_count,
                "total_pages": total_pages,
                "page": page,
            }

    def rewind_music_track(self, track_id: int):
        with Session(autoflush=False, bind=engine) as db:
            track = db.query(MusicPlaylistTrack).filter_by(id=track_id).first()
            if not track:
                return

            now = datetime.utcnow()
            track.status = "pending"
            track.started_at = None
            track.finished_at = None
            track.error_message = None
            track.updated_at = now

            playlist = db.query(MusicPlaylist).filter_by(id=track.playlist_id).first()
            if playlist:
                playlist.updated_at = now

            db.commit()

    def mark_music_track_status(self, track_id: int, status: str, error_message: str | None = None):
        with Session(autoflush=False, bind=engine) as db:
            track = db.query(MusicPlaylistTrack).filter_by(id=track_id).first()
            if not track:
                return

            now = datetime.utcnow()
            track.status = status
            track.error_message = error_message
            track.updated_at = now
            if status == "pending":
                track.started_at = None
                track.finished_at = None
            if status == "playing":
                track.started_at = now
            if status in {"played", "skipped", "error"}:
                track.finished_at = now

            playlist = db.query(MusicPlaylist).filter_by(id=track.playlist_id).first()
            if playlist:
                playlist.updated_at = now

            db.commit()

    def reset_music_playing_tracks(self):
        with Session(autoflush=False, bind=engine) as db:
            now = datetime.utcnow()
            tracks = db.query(MusicPlaylistTrack).filter_by(status="playing").all()
            for track in tracks:
                track.status = "pending"
                track.started_at = None
                track.updated_at = now

            db.commit()

    def clear_music_playlist(self, guild_id: int, user_id: int):
        with Session(autoflush=False, bind=engine) as db:
            playlist = (
                db.query(MusicPlaylist)
                .filter_by(guild_id=guild_id, user_id=user_id, is_active=True)
                .first()
            )
            if not playlist:
                return 0

            deleted_count = (
                db.query(MusicPlaylistTrack)
                .filter_by(playlist_id=playlist.id)
                .delete(synchronize_session=False)
            )
            playlist.updated_at = datetime.utcnow()
            db.commit()
            return deleted_count

    def get_music_playlist_stats(self, guild_id: int, user_id: int) -> dict:
        with Session(autoflush=False, bind=engine) as db:
            playlist = (
                db.query(MusicPlaylist)
                .filter_by(guild_id=guild_id, user_id=user_id, is_active=True)
                .first()
            )
            if not playlist:
                return {"pending_count": 0, "played_count": 0, "error_count": 0}

            rows = db.query(MusicPlaylistTrack.status).filter_by(playlist_id=playlist.id).all()
            statuses = [row[0] for row in rows]
            return {
                "pending_count": sum(status in self.MUSIC_PENDING_STATUSES for status in statuses),
                "played_count": statuses.count("played"),
                "error_count": statuses.count("error"),
            }

    def create_update_contest(self, guild_id: int, channel_id: int, emoji_str: str, status: bool):
        with Session(autoflush=False, bind=engine) as db:
            # Старую таблицу сохраняем для обратной совместимости.
            existing_contest = db.query(Contests).filter_by(guild_id=guild_id, channel_id=channel_id).first()

            if existing_contest:
                existing_contest.emoji_str = emoji_str
                existing_contest.status = status
            else:
                contest = Contests(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    emoji_str=emoji_str,
                    status=status,
                )
                db.add(contest)

            db.commit()

    def start_contest_run(self, guild_id: int, channel_id: int, contest_name: str, emoji_str: str):
        with Session(autoflush=False, bind=engine) as db:
            contest = (
                db.query(ContestRun)
                .filter_by(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    contest_name=contest_name,
                    is_active=True,
                )
                .first()
            )

            if contest:
                contest.emoji_str = emoji_str
            else:
                contest = ContestRun(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    contest_name=contest_name,
                    emoji_str=emoji_str,
                    is_active=True,
                )
                db.add(contest)
                db.flush()

            db.commit()
            db.refresh(contest)
            return contest

    def stop_contest_run(self, guild_id: int, channel_id: int, contest_name: str):
        with Session(autoflush=False, bind=engine) as db:
            contest = (
                db.query(ContestRun)
                .filter_by(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    contest_name=contest_name,
                    is_active=True,
                )
                .first()
            )

            if not contest:
                return None

            contest.is_active = False
            db.commit()
            db.refresh(contest)
            return contest

    def get_active_contests_for_channel(self, guild_id: int, channel_id: int):
        with Session(autoflush=False, bind=engine) as db:
            return (
                db.query(ContestRun)
                .filter_by(guild_id=guild_id, channel_id=channel_id, is_active=True)
                .all()
            )

    def add_contest_message(self, contest_id: int, message_id: int):
        with Session(autoflush=False, bind=engine) as db:
            existing_message = (
                db.query(ContestMessage)
                .filter_by(contest_id=contest_id, message_id=message_id)
                .first()
            )

            if existing_message:
                return existing_message

            contest_message = ContestMessage(contest_id=contest_id, message_id=message_id)
            db.add(contest_message)
            db.commit()
            db.refresh(contest_message)
            return contest_message

    def get_contest_messages(self, contest_id: int):
        with Session(autoflush=False, bind=engine) as db:
            return (
                db.query(ContestMessage)
                .filter_by(contest_id=contest_id)
                .order_by(ContestMessage.id.asc())
                .all()
            )

    def create_giveaway(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
        admin_channel_id: int,
        creator_id: int,
        emoji_str: str,
        description: str,
        winner_count: int,
    ):
        with Session(autoflush=False, bind=engine) as db:
            giveaway = Giveaway(
                guild_id=guild_id,
                channel_id=channel_id,
                message_id=message_id,
                admin_channel_id=admin_channel_id,
                creator_id=creator_id,
                emoji_str=emoji_str,
                description=description,
                winner_count=winner_count,
                is_active=True,
            )
            db.add(giveaway)
            db.commit()
            db.refresh(giveaway)
            return giveaway

    def update_giveaway_admin_message(self, giveaway_id: int, admin_message_id: int):
        with Session(autoflush=False, bind=engine) as db:
            giveaway = db.query(Giveaway).filter_by(id=giveaway_id).first()
            if not giveaway:
                return None

            giveaway.admin_message_id = admin_message_id
            db.commit()
            db.refresh(giveaway)
            return giveaway

    def get_active_giveaway_by_message(self, guild_id: int, channel_id: int, message_id: int):
        with Session(autoflush=False, bind=engine) as db:
            return (
                db.query(Giveaway)
                .filter_by(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    message_id=message_id,
                    is_active=True,
                )
                .first()
            )

    def get_active_giveaway_by_admin_message(self, guild_id: int, admin_channel_id: int, admin_message_id: int):
        with Session(autoflush=False, bind=engine) as db:
            return (
                db.query(Giveaway)
                .filter_by(
                    guild_id=guild_id,
                    admin_channel_id=admin_channel_id,
                    admin_message_id=admin_message_id,
                    is_active=True,
                )
                .first()
            )

    def add_giveaway_participant(self, giveaway_id: int, user_id: int):
        with Session(autoflush=False, bind=engine) as db:
            participant = (
                db.query(GiveawayParticipant)
                .filter_by(giveaway_id=giveaway_id, user_id=user_id)
                .first()
            )

            if participant:
                participant.is_active = True
                participant.left_at = None
                db.commit()
                db.refresh(participant)
                return participant

            participant = GiveawayParticipant(giveaway_id=giveaway_id, user_id=user_id)
            db.add(participant)
            db.commit()
            db.refresh(participant)
            return participant

    def deactivate_giveaway_participant(self, giveaway_id: int, user_id: int):
        with Session(autoflush=False, bind=engine) as db:
            participant = (
                db.query(GiveawayParticipant)
                .filter_by(giveaway_id=giveaway_id, user_id=user_id)
                .first()
            )

            if participant and participant.is_active:
                participant.is_active = False
                participant.left_at = datetime.utcnow()
                db.commit()

    def sync_giveaway_participants(self, giveaway_id: int, active_user_ids: list[int]) -> list[int]:
        active_user_ids = list(dict.fromkeys(active_user_ids))
        active_user_id_set = set(active_user_ids)

        with Session(autoflush=False, bind=engine) as db:
            participants = (
                db.query(GiveawayParticipant)
                .filter_by(giveaway_id=giveaway_id)
                .all()
            )
            participants_by_user_id = {
                participant.user_id: participant
                for participant in participants
            }

            # Перед завершением приводим БД к фактическим реакциям под сообщением.
            for participant in participants:
                if participant.user_id in active_user_id_set:
                    participant.is_active = True
                    participant.left_at = None
                elif participant.is_active:
                    participant.is_active = False
                    participant.left_at = datetime.utcnow()

            for user_id in active_user_ids:
                if user_id not in participants_by_user_id:
                    db.add(
                        GiveawayParticipant(
                            giveaway_id=giveaway_id,
                            user_id=user_id,
                            is_active=True,
                        )
                    )

            db.commit()
            return active_user_ids

    def get_active_giveaway_participant_ids(self, giveaway_id: int) -> list[int]:
        with Session(autoflush=False, bind=engine) as db:
            participants = (
                db.query(GiveawayParticipant)
                .filter_by(giveaway_id=giveaway_id, is_active=True)
                .order_by(GiveawayParticipant.joined_at.asc())
                .all()
            )
            return [participant.user_id for participant in participants]

    def get_giveaway_stats(self, giveaway_id: int) -> dict[str, int]:
        with Session(autoflush=False, bind=engine) as db:
            active_count = (
                db.query(GiveawayParticipant)
                .filter_by(giveaway_id=giveaway_id, is_active=True)
                .count()
            )
            left_count = (
                db.query(GiveawayParticipant)
                .filter_by(giveaway_id=giveaway_id, is_active=False)
                .count()
            )

            return {
                "active_count": active_count,
                "left_count": left_count,
                "total_count": active_count + left_count,
            }

    def finish_giveaway(self, giveaway_id: int, winner_ids: list[int]):
        with Session(autoflush=False, bind=engine) as db:
            giveaway = db.query(Giveaway).filter_by(id=giveaway_id, is_active=True).first()
            if not giveaway:
                return None

            giveaway.is_active = False
            giveaway.finished_at = datetime.utcnow()
            for winner_id in winner_ids:
                db.add(GiveawayWin(giveaway_id=giveaway_id, user_id=winner_id))

            db.commit()
            db.refresh(giveaway)
            return giveaway

    # Обновление статуса отслеживания канала.
    def create_update_channel_statistic(self, guild_id: int, channel_id: int, status: bool):
        with Session(autoflush=False, bind=engine) as db:
            existing_channel = db.query(TrackedChannel).filter_by(guild_id=guild_id, channel_id=channel_id).first()

            if existing_channel:
                existing_channel.is_active = status
            else:
                statistic = TrackedChannel(guild_id=guild_id, channel_id=channel_id, is_active=status)
                db.add(statistic)

            db.commit()

    # Получение всех отслеживаемых каналов для статистики.
    def get_all_statistics_channel():
        with Session(autoflush=False, bind=engine) as db:
            channels = db.query(TrackedChannel).filter_by(is_active=True).all()
            return [channel.channel_id for channel in channels]

    # Счёт сообщений.
    def update_message_statistic(self, channel_id: int, today):
        with Session(autoflush=False, bind=engine) as db:
            stat = db.query(MessageStatistics).filter_by(channel_id=channel_id, date=today).first()
            if stat:
                stat.message_count += 1
            else:
                stat = MessageStatistics(channel_id=channel_id, date=today, message_count=0)
                db.add(stat)

            db.commit()

    def get_yesterday_statistic(channel_id: int, date):
        with Session(autoflush=False, bind=engine) as db:
            stats = db.query(MessageStatistics).filter_by(channel_id=channel_id, date=date).first()
            return stats

    def create_update_recruitment_channel(self, guild_id, channel_id):
        with Session(autoflush=False, bind=engine) as db:
            existing_recruitment = db.query(Recruitments).filter_by(guild_id=guild_id).first()

            if existing_recruitment:
                existing_recruitment.channel_id = channel_id
            else:
                recruitment = Recruitments(guild_id=guild_id, channel_id=channel_id)
                db.add(recruitment)

            db.commit()

    def create_update_recruitment_message(self, guild_id, message_id):
        with Session(autoflush=False, bind=engine) as db:
            existing_recruitment = db.query(Recruitments).filter_by(guild_id=guild_id).first()

            if existing_recruitment:
                existing_recruitment.message_id = message_id
            else:
                recruitment = Recruitments(guild_id=guild_id, message_id=message_id)
                db.add(recruitment)

            db.commit()

    def get_recruitment_by_guild(self, guild_id):
        with Session(autoflush=False, bind=engine) as db:
            recruitment = db.query(Recruitments).filter_by(guild_id=guild_id).first()
            return recruitment

    def replace_recruitment_positions(self, guild_id: int, positions: list[dict]):
        with Session(autoflush=False, bind=engine) as db:
            db.query(RecruitmentPosition).filter_by(guild_id=guild_id).delete()

            for index, position in enumerate(positions):
                db.add(
                    RecruitmentPosition(
                        guild_id=guild_id,
                        title=position["title"],
                        description=position["description"],
                        sort_order=index,
                    )
                )

            db.commit()

    def get_recruitment_positions(self, guild_id: int):
        with Session(autoflush=False, bind=engine) as db:
            return (
                db.query(RecruitmentPosition)
                .filter_by(guild_id=guild_id)
                .order_by(RecruitmentPosition.sort_order.asc())
                .all()
            )

    def replace_recruitment_questions(self, guild_id: int, questions: list[dict]):
        with Session(autoflush=False, bind=engine) as db:
            db.query(RecruitmentQuestion).filter_by(guild_id=guild_id).delete()

            for index, question in enumerate(questions):
                db.add(
                    RecruitmentQuestion(
                        guild_id=guild_id,
                        label=question["label"],
                        placeholder=question["placeholder"],
                        style=question["style"],
                        sort_order=index,
                    )
                )

            db.commit()

    def get_recruitment_questions(self, guild_id: int):
        with Session(autoflush=False, bind=engine) as db:
            return (
                db.query(RecruitmentQuestion)
                .filter_by(guild_id=guild_id)
                .order_by(RecruitmentQuestion.sort_order.asc())
                .all()
            )

    # Обновление статуса отслеживания анонимного канала.
    def create_update_channel_anonimus(self, guild_id: int, channel_id: int, status: bool):
        with Session(autoflush=False, bind=engine) as db:
            existing_channel = (
                db.query(TrackedAnonimusChannel)
                .filter_by(guild_id=guild_id, channel_id=channel_id)
                .first()
            )

            if existing_channel:
                existing_channel.is_active = status
            else:
                statistic = TrackedAnonimusChannel(guild_id=guild_id, channel_id=channel_id, is_active=status)
                db.add(statistic)

            db.commit()

    # Получение всех анонимных каналов.
    def get_all_anonimus_channel(self):
        with Session(autoflush=False, bind=engine) as db:
            channels = db.query(TrackedAnonimusChannel).filter_by(is_active=True).all()
            return [channel.channel_id for channel in channels]
