-- OpenOps Project Knowledge Database Schema
-- This schema stores project analysis, services, and deployment information.

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    keypoints TEXT DEFAULT '[]',  -- JSON array
    analyzed_at DATETIME,
    updated_at DATETIME
);

-- Services table
CREATE TABLE IF NOT EXISTS services (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    description TEXT DEFAULT '',
    type TEXT,  -- frontend, backend, worker, database
    framework TEXT,
    language TEXT,
    version TEXT,
    entry_point TEXT,
    build_command TEXT,
    start_command TEXT,
    port INTEGER,
    env_vars TEXT DEFAULT '[]',  -- JSON array
    dependencies TEXT DEFAULT '[]',  -- JSON array of service IDs
    keypoints TEXT DEFAULT '[]'  -- JSON array
);

-- Deployments table
CREATE TABLE IF NOT EXISTS deployments (
    id TEXT PRIMARY KEY,
    service_id TEXT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,  -- vercel, railway, render
    url TEXT,
    dashboard_url TEXT,
    deployed_at DATETIME,
    config TEXT DEFAULT '{}',  -- JSON object
    status TEXT DEFAULT 'active'  -- active, failed, superseded
);

-- Service dependencies (relational table for efficient reverse lookups)
CREATE TABLE IF NOT EXISTS service_dependencies (
    service_id TEXT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    depends_on_id TEXT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    PRIMARY KEY (service_id, depends_on_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_projects_path ON projects(path);
CREATE INDEX IF NOT EXISTS idx_services_project ON services(project_id);
CREATE INDEX IF NOT EXISTS idx_deployments_service ON deployments(service_id);
CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
CREATE INDEX IF NOT EXISTS idx_service_deps_depends_on ON service_dependencies(depends_on_id);
