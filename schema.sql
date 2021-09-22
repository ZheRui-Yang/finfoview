DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS topics;
DROP TABLE IF EXISTS regions;

-- Do we need a table referencing picture urls?

CREATE TABLE topics (
  id TINYINT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT,
  name CHAR(4) NOT NULL
) ENGINE = InnoDB;

CREATE TABLE regions (
  id TINYINT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT,
  name CHAR(2) NOT NULL,
  includings VARCHAR(100)
) ENGINE = InnoDB;

CREATE TABLE users (
  id INT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(30) NOT NULL,
  insurer_or_salesman BOOLEAN,  -- true: insurer, false: salesman
  sex BOOLEAN,  -- true if male, false if female
  region_id TINYINT UNSIGNED,
  CONSTRAINT `fk_user_region`
    FOREIGN KEY (region_id) REFERENCES regions (id)
) ENGINE = InnoDB;

CREATE TABLE posts (
  id INT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT, 
  post_id INT UNSIGNED NOT NULL, -- post id of finfo.tw
  title VARCHAR(100) NOT NULL, 
  position SMALLINT UNSIGNED NOT NULL,  -- 0: main, others: reply
  create_time DATETIME NOT NULL,
  author_id INT UNSIGNED,
  topic_id TINYINT UNSIGNED,
  content TEXT,
  CONSTRAINT `fk_post_author`
    FOREIGN KEY (author_id) REFERENCES users (id)
    ON DELETE SET NULL
    ON UPDATE RESTRICT,
  CONSTRAINT `fk_post_topic`
    FOREIGN KEY (topic_id) REFERENCES topics (id)
    ON DELETE SET NULL
    ON UPDATE RESTRICT
) ENGINE = InnoDB;

-- These tables are never be changed
INSERT INTO topics (name)
VALUES ('投保規劃'), ('保單健檢'), ('理賠申請'),
       ('保單解約'), ('保險觀念');

INSERT INTO regions (name, includings)
VALUES ('北部', '基隆市、臺北市、新北市、桃園市、新竹縣市、宜蘭縣'), 
      ('中部', '新竹縣市、苗栗縣市、台中市、彰化縣、南投縣、雲林縣'),
      ('南部', '南投縣、雲林縣、嘉義縣市、台南縣市、高雄市、屏東縣'),
      ('東部', '');
