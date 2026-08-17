CREATE TABLE `lotto_draws` (
	`id` int AUTO_INCREMENT NOT NULL,
	`drawNo` int NOT NULL,
	`drawDate` timestamp NOT NULL,
	`main1` int NOT NULL,
	`main2` int NOT NULL,
	`main3` int NOT NULL,
	`main4` int NOT NULL,
	`main5` int NOT NULL,
	`main6` int NOT NULL,
	`special` int NOT NULL,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `lotto_draws_id` PRIMARY KEY(`id`),
	CONSTRAINT `lotto_draws_drawNo_unique` UNIQUE(`drawNo`)
);
--> statement-breakpoint
CREATE TABLE `lotto_number_stats` (
	`id` int AUTO_INCREMENT NOT NULL,
	`number` int NOT NULL,
	`frequency50` int NOT NULL,
	`gap` int NOT NULL,
	`temperature` varchar(16) NOT NULL,
	`modelWeight` int NOT NULL,
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `lotto_number_stats_id` PRIMARY KEY(`id`),
	CONSTRAINT `lotto_number_stats_number_unique` UNIQUE(`number`)
);
--> statement-breakpoint
CREATE TABLE `lotto_recommendations` (
	`id` int AUTO_INCREMENT NOT NULL,
	`setIndex` int NOT NULL,
	`numbers` text NOT NULL,
	`oddEven` varchar(24) NOT NULL,
	`numberSum` int NOT NULL,
	`consecutivePairs` int NOT NULL,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `lotto_recommendations_id` PRIMARY KEY(`id`),
	CONSTRAINT `lotto_recommendations_setIndex_unique` UNIQUE(`setIndex`)
);
