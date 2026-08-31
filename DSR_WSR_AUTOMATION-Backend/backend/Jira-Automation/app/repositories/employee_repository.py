from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.models.employee import Employee, EmployeeTrack
from app.models.team import Team


class EmployeeRepository:
    """Data access layer for employees and their track assignments."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_team_by_name(self, team_name: str) -> Team | None:
        stmt = select(Team).where(Team.team_name == team_name)
        return self.db.scalars(stmt).first()

    def get_team_by_id(self, team_id: int) -> Team | None:
        return self.db.get(Team, team_id)

    def get_employee_by_id(self, employee_id: int) -> Employee | None:
        stmt = (
            select(Employee)
            .options(
                joinedload(Employee.team),
                joinedload(Employee.track_assignments).joinedload(EmployeeTrack.project),
            )
            .where(Employee.employee_id == employee_id)
        )
        return self.db.scalars(stmt).unique().first()

    def list_employees_for_team(
        self,
        team_id: int,
        *,
        active_only: bool = False,
    ) -> list[Employee]:
        stmt = (
            select(Employee)
            .options(
                joinedload(Employee.team),
                joinedload(Employee.track_assignments).joinedload(EmployeeTrack.project),
            )
            .where(Employee.team_id == team_id)
            .order_by(Employee.employee_name, Employee.employee_id)
        )
        employees = list(self.db.scalars(stmt).unique().all())
        if not active_only:
            return employees

        filtered: list[Employee] = []
        for employee in employees:
            active_assignments = [
                a
                for a in employee.track_assignments
                if a.is_active and (a.project is None or a.project.is_active)
            ]
            if active_assignments:
                employee.track_assignments = active_assignments
                filtered.append(employee)
        return filtered

    def list_employees_for_track(
        self,
        project_id: int,
        *,
        active_only: bool = False,
    ) -> list[EmployeeTrack]:
        stmt = (
            select(EmployeeTrack)
            .options(
                joinedload(EmployeeTrack.employee).joinedload(Employee.team),
                joinedload(EmployeeTrack.project),
            )
            .join(EmployeeTrack.employee)
            .where(EmployeeTrack.project_id == project_id)
            .order_by(Employee.employee_name)
        )
        if active_only:
            stmt = stmt.where(EmployeeTrack.is_active.is_(True))

        return list(self.db.scalars(stmt).unique().all())

    def get_employee_by_name(self, team_id: int, employee_name: str) -> Employee | None:
        normalized = employee_name.strip()
        if not normalized:
            return None
        stmt = select(Employee).where(
            Employee.team_id == team_id,
            Employee.employee_name == normalized,
        )
        return self.db.scalars(stmt).first()

    def get_employee_by_name_ci(self, team_id: int, employee_name: str) -> Employee | None:
        normalized = employee_name.strip()
        if not normalized:
            return None
        stmt = select(Employee).where(
            Employee.team_id == team_id,
            func.lower(Employee.employee_name) == normalized.lower(),
        )
        return self.db.scalars(stmt).first()

    def create_employee(
        self,
        *,
        employee_name: str,
        team_id: int,
    ) -> Employee:
        employee = Employee(employee_name=employee_name.strip(), team_id=team_id)
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return employee

    def add_track_assignment(
        self,
        *,
        employee_id: int,
        project_id: int,
        is_active: bool = True,
    ) -> EmployeeTrack:
        assignment = EmployeeTrack(
            employee_id=employee_id,
            project_id=project_id,
            is_active=is_active,
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def get_track_assignment(
        self,
        employee_id: int,
        project_id: int,
    ) -> EmployeeTrack | None:
        stmt = select(EmployeeTrack).where(
            EmployeeTrack.employee_id == employee_id,
            EmployeeTrack.project_id == project_id,
        )
        return self.db.scalars(stmt).first()

    def update_track_assignment(
        self,
        assignment: EmployeeTrack,
        *,
        is_active: bool,
    ) -> EmployeeTrack:
        assignment.is_active = is_active
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def deactivate_assignments_for_track(self, project_id: int) -> int:
        """Set inactive on all currently active assignee rows for a track."""
        stmt = (
            update(EmployeeTrack)
            .where(
                EmployeeTrack.project_id == project_id,
                EmployeeTrack.is_active.is_(True),
            )
            .values(is_active=False)
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return int(result.rowcount or 0)

    def delete_track_assignment(self, assignment: EmployeeTrack) -> None:
        self.db.delete(assignment)
        self.db.commit()
