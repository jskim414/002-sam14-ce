PRAGMA foreign_keys=ON;
CREATE TABLE schema_version(version INTEGER PRIMARY KEY, description TEXT NOT NULL);
INSERT INTO schema_version VALUES(5,'CE catalog provenance, level values and evidence gates');
CREATE TABLE release_profile(
 id TEXT PRIMARY KEY, build_id TEXT NOT NULL, locale TEXT NOT NULL,
 ruleset TEXT NOT NULL, inventory_sha256 TEXT NOT NULL,
 profile_sha256 TEXT NOT NULL, parser_sha256 TEXT NOT NULL, git_sha TEXT,
 captured_at TEXT NOT NULL, release_ready INTEGER NOT NULL CHECK(release_ready IN(0,1)),
 blockers_json TEXT NOT NULL
);
CREATE TABLE source_file(
 id INTEGER PRIMARY KEY, relative_path TEXT NOT NULL UNIQUE,
 sha256 TEXT NOT NULL CHECK(length(sha256)=64), size_bytes INTEGER NOT NULL,
 processing_status TEXT NOT NULL, notes TEXT
);
CREATE TABLE content_pack(
 id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT,
 steam_app_id INTEGER, installed INTEGER NOT NULL CHECK(installed IN(0,1)),
 ownership_status TEXT NOT NULL, evidence TEXT NOT NULL
);
CREATE TABLE scenario(
 id TEXT PRIMARY KEY, source_code INTEGER NOT NULL UNIQUE,
 name TEXT NOT NULL, start_year INTEGER, start_month INTEGER,
 mode TEXT NOT NULL, mode_verification TEXT NOT NULL,
 source_file_id INTEGER NOT NULL REFERENCES source_file(id),
 status TEXT NOT NULL CHECK(status IN('PARSED_REVIEW','PENDING')),
 expected_rows INTEGER, record_slots INTEGER, delivery_status TEXT NOT NULL
);
CREATE TABLE dictionary(
 kind TEXT NOT NULL, id INTEGER NOT NULL, name TEXT NOT NULL,
 source_file_id INTEGER NOT NULL REFERENCES source_file(id), record_offset INTEGER NOT NULL,
 PRIMARY KEY(kind,id)
);
CREATE TABLE officer(
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, courtesy_name TEXT NOT NULL,
 kind TEXT NOT NULL, kind_verification TEXT NOT NULL
);
CREATE TABLE officer_state(
 scenario_id TEXT NOT NULL REFERENCES scenario(id), officer_id INTEGER NOT NULL REFERENCES officer(id),
 name TEXT NOT NULL, state TEXT NOT NULL, raw_state INTEGER NOT NULL,
 force_id INTEGER, force_name TEXT, settlement_id INTEGER, settlement_name TEXT,
 appearance_year INTEGER, birth_year INTEGER, death_year INTEGER,
 leadership INTEGER NOT NULL, strength INTEGER NOT NULL, intelligence INTEGER NOT NULL,
 politics INTEGER NOT NULL, charisma INTEGER NOT NULL, affinity INTEGER,
 doctrine_id INTEGER, doctrine TEXT, policy_id INTEGER, policy TEXT, policy_level INTEGER,
 record_offset INTEGER NOT NULL, record_sha256 TEXT NOT NULL,
 verification TEXT NOT NULL, PRIMARY KEY(scenario_id,officer_id)
);
CREATE TABLE officer_personality(
 scenario_id TEXT NOT NULL, officer_id INTEGER NOT NULL,
 integrity INTEGER, diplomacy INTEGER, han_attitude INTEGER, ambition INTEGER, aggression INTEGER,
 verification TEXT NOT NULL CHECK(verification IN('UNKNOWN','VERIFIED','CROSS_CHECKED','NOT_APPLICABLE','CONFLICT')),
 PRIMARY KEY(scenario_id,officer_id),
 FOREIGN KEY(scenario_id,officer_id) REFERENCES officer_state(scenario_id,officer_id)
);
CREATE TABLE personality_evidence(
 scenario_id TEXT NOT NULL, officer_id INTEGER NOT NULL, field TEXT NOT NULL,
 raw_value INTEGER NOT NULL, record_offset INTEGER NOT NULL, encoding TEXT NOT NULL,
 PRIMARY KEY(scenario_id,officer_id,field),
 FOREIGN KEY(scenario_id,officer_id) REFERENCES officer_personality(scenario_id,officer_id)
);
CREATE TABLE officer_kinship(
 scenario_id TEXT NOT NULL, officer_id INTEGER NOT NULL,
 spouse_id INTEGER REFERENCES officer(id), sworn_group_id INTEGER REFERENCES officer(id),
 PRIMARY KEY(scenario_id,officer_id),
 FOREIGN KEY(scenario_id,officer_id) REFERENCES officer_state(scenario_id,officer_id)
);
CREATE TABLE dictionary_detail(
 kind TEXT NOT NULL, dictionary_id INTEGER NOT NULL, description TEXT NOT NULL,
 verification TEXT NOT NULL, PRIMARY KEY(kind,dictionary_id),
 FOREIGN KEY(kind,dictionary_id) REFERENCES dictionary(kind,id)
);
CREATE TABLE policy_component(
 policy_id INTEGER NOT NULL, component_id INTEGER NOT NULL, slot INTEGER NOT NULL,
 PRIMARY KEY(policy_id,slot)
);
CREATE TABLE dictionary_attribute(
 kind TEXT NOT NULL, dictionary_id INTEGER NOT NULL, attributes_json TEXT NOT NULL,
 PRIMARY KEY(kind,dictionary_id),
 FOREIGN KEY(kind,dictionary_id) REFERENCES dictionary(kind,id)
);
CREATE TABLE dictionary_text_source(
 kind TEXT NOT NULL, dictionary_id INTEGER NOT NULL, source_file_id INTEGER NOT NULL REFERENCES source_file(id),
 message_id INTEGER NOT NULL, record_offset INTEGER NOT NULL,
 PRIMARY KEY(kind,dictionary_id),
 FOREIGN KEY(kind,dictionary_id) REFERENCES dictionary(kind,id)
);
CREATE TABLE policy_level_effect(
 effect_id INTEGER NOT NULL, level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 10),
 raw_value INTEGER NOT NULL, unit TEXT, verification TEXT NOT NULL,
 source_file_id INTEGER NOT NULL REFERENCES source_file(id), record_offset INTEGER NOT NULL,
 PRIMARY KEY(effect_id,level)
);
CREATE TABLE semantic_evidence(
 key TEXT PRIMARY KEY, status TEXT NOT NULL, evidence_json TEXT NOT NULL
);
CREATE TABLE officer_dictionary(
 scenario_id TEXT NOT NULL, officer_id INTEGER NOT NULL,
 kind TEXT NOT NULL, dictionary_id INTEGER NOT NULL, slot INTEGER NOT NULL,
 PRIMARY KEY(scenario_id,officer_id,kind,slot),
 FOREIGN KEY(scenario_id,officer_id) REFERENCES officer_state(scenario_id,officer_id),
 FOREIGN KEY(kind,dictionary_id) REFERENCES dictionary(kind,id)
);
CREATE TABLE relationship_scope(
 id INTEGER PRIMARY KEY, scenario_id TEXT NOT NULL UNIQUE REFERENCES scenario(id),
 semantics TEXT NOT NULL CHECK(semantics='SCENARIO_COMPLETE_RECORDS'), verification TEXT NOT NULL
);
CREATE TABLE relationship_edge(
 scope_id INTEGER NOT NULL REFERENCES relationship_scope(id),
 from_officer_id INTEGER NOT NULL REFERENCES officer(id),
 to_officer_id INTEGER NOT NULL REFERENCES officer(id),
 type TEXT NOT NULL CHECK(type IN('AFFINITY','DISLIKE','MARRIAGE','SWORN_SIBLING')),
 slot INTEGER NOT NULL, record_offset INTEGER NOT NULL,
 CHECK(from_officer_id<>to_officer_id),
 PRIMARY KEY(scope_id,from_officer_id,to_officer_id,type)
);
CREATE TABLE coverage(
 key TEXT PRIMARY KEY, expected INTEGER, actual INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN('PASS','PARTIAL','PENDING','FAIL')), note TEXT NOT NULL
);
CREATE INDEX state_filter ON officer_state(scenario_id,state,force_id);
CREATE INDEX policy_filter ON officer_state(scenario_id,policy_id,policy_level);
CREATE INDEX dictionary_filter ON officer_dictionary(scenario_id,kind,dictionary_id,officer_id);
CREATE INDEX relationship_incoming ON relationship_edge(scope_id,to_officer_id,type);
