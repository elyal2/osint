#!/usr/bin/env python3
"""
Utilidad para resetear la base de datos Neo4j.
Este script elimina todos los nodos y relaciones de la base de datos.
"""

import argparse
import sys
import logging
from graph_database import EntityGraph
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def main():
    parser = argparse.ArgumentParser(
        description="Resetea la base de datos Neo4j, eliminando todos los nodos y relaciones."
    )
    
    parser.add_argument(
        "--force", 
        action="store_true",
        help="Fuerza el reseteo sin solicitar confirmación"
    )
    
    args = parser.parse_args()
    
    # Connect to database
    try:
        graph_db = EntityGraph()
        logger.info("Conectado a la base de datos Neo4j")
    except Exception as e:
        logger.error(f"Error al conectar con Neo4j: {str(e)}")
        sys.exit(1)
    
    try:
        if args.force:
            # Reset database without additional confirmation
            result = graph_db.reset_database(confirm=True)
            if result:
                logger.info("Base de datos reseteada exitosamente")
            else:
                logger.error("No se pudo resetear completamente la base de datos")
                sys.exit(1)
        else:
            # Ask for confirmation
            confirm = input("¿Estás seguro de que quieres resetear la base de datos? Esta acción NO se puede deshacer. [s/N]: ")
            if confirm.lower() in ['s', 'si', 'sí', 'y', 'yes']:
                result = graph_db.reset_database(confirm=True)
                if result:
                    logger.info("Base de datos reseteada exitosamente")
                else:
                    logger.error("No se pudo resetear completamente la base de datos")
                    sys.exit(1)
            else:
                logger.info("Operación cancelada por el usuario")
    except KeyboardInterrupt:
        logger.info("Operación cancelada por el usuario")
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        sys.exit(1)
    finally:
        # Close database connection
        if graph_db:
            graph_db.close()

if __name__ == "__main__":
    main()