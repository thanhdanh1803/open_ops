"""Abstract storage interfaces for OpenOps."""

import logging
from abc import ABC, abstractmethod

from openops.models import Deployment, Project, Service

logger = logging.getLogger(__name__)


class ProjectStoreBase(ABC):
    """Abstract base class for project knowledge storage.

    Implementations of this interface provide persistence for
    project metadata, services, and deployment information.
    """

    @abstractmethod
    def upsert_project(self, project: Project) -> None:
        """Insert or update a project.

        Args:
            project: The project to upsert
        """
        pass

    @abstractmethod
    def get_project(self, path: str) -> Project | None:
        """Get a project by its path.

        Args:
            path: Absolute path to the project

        Returns:
            The project if found, None otherwise
        """
        pass

    @abstractmethod
    def get_project_by_id(self, project_id: str) -> Project | None:
        """Get a project by its ID.

        Args:
            project_id: UUID of the project

        Returns:
            The project if found, None otherwise
        """
        pass

    @abstractmethod
    def list_projects(self) -> list[Project]:
        """List all known projects.

        Returns:
            List of all projects in storage
        """
        pass

    @abstractmethod
    def delete_project(self, project_id: str) -> bool:
        """Delete a project and all associated data.

        Args:
            project_id: UUID of the project to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def upsert_service(self, service: Service) -> None:
        """Insert or update a service.

        Args:
            service: The service to upsert
        """
        pass

    @abstractmethod
    def get_service(self, service_id: str) -> Service | None:
        """Get a service by its ID.

        Args:
            service_id: UUID of the service

        Returns:
            The service if found, None otherwise
        """
        pass

    @abstractmethod
    def get_services_for_project(self, project_id: str) -> list[Service]:
        """Get all services for a project.

        Args:
            project_id: UUID of the project

        Returns:
            List of services belonging to the project
        """
        pass

    @abstractmethod
    def delete_service(self, service_id: str) -> bool:
        """Delete a service.

        Args:
            service_id: UUID of the service to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def add_deployment(self, deployment: Deployment) -> None:
        """Record a new deployment.

        This should also mark any previous active deployments
        for the same service as 'superseded'.

        Args:
            deployment: The deployment to record
        """
        pass

    @abstractmethod
    def get_active_deployment(self, service_id: str) -> Deployment | None:
        """Get the active deployment for a service.

        Args:
            service_id: UUID of the service

        Returns:
            The active deployment if exists, None otherwise
        """
        pass

    @abstractmethod
    def get_deployments_for_service(self, service_id: str) -> list[Deployment]:
        """Get all deployments for a service.

        Args:
            service_id: UUID of the service

        Returns:
            List of all deployments for the service, ordered by deployed_at desc
        """
        pass

    def get_project_summary(self, path: str) -> dict | None:
        """Get full project summary with services and deployments.

        This is a convenience method that aggregates project data.
        Implementations may override for optimization.

        Args:
            path: Absolute path to the project

        Returns:
            Dictionary with project, services, and deployment info, or None if not found
        """
        project = self.get_project(path)
        if not project:
            return None

        services = self.get_services_for_project(project.id)

        return {
            "project": project,
            "services": [
                {
                    "service": service,
                    "deployment": self.get_active_deployment(service.id),
                }
                for service in services
            ],
        }


__all__ = ["ProjectStoreBase"]
