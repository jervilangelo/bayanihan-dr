-- Runs once, when the PostgreSQL data volume is first initialised.
-- Creates an isolated database used only by the automated test suite.
CREATE DATABASE cms_test;
