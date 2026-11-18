import type { AcademicProgram } from '../../../../packages/shared-types/src/scheduling';
import programs from '../../../../packages/api-contracts/classync_contracts/catalogs/programs.json';

// The source is the repository's supplied catalog, not a Registrar-approved active-term list.
export const suppliedAcademicProgramCatalog = programs as unknown as readonly AcademicProgram[];
