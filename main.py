import argparse
import json
import os
import sys
from pathlib import Path
from entity_extractor_improved import EnhancedEntityRelationshipExtractor as EntityRelationshipExtractor
from web_scraper import fetch_web_content
from graph_database import EntityGraph
from config import AppConfig, LLMConfig
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_text_file(file_path: str) -> str:
    """
    Load text from a file, handling different encodings.
    
    Args:
        file_path (str): Path to the text file
        
    Returns:
        str: Content of the text file
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        IOError: If there's an error reading the file
    """
    try:
        # Try UTF-8 first
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except UnicodeDecodeError:
        # If UTF-8 fails, try with latin-1
        try:
            with open(file_path, 'r', encoding='latin-1') as file:
                return file.read()
        except Exception as e:
            raise IOError(f"Error reading file with latin-1 encoding: {str(e)}")
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except Exception as e:
        raise IOError(f"Error reading file: {str(e)}")

def load_pdf_file(file_path: str) -> bytes:
    """Loads a PDF file in binary mode."""
    try:
        with open(file_path, 'rb') as file:
            return file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
    except Exception as e:
        raise IOError(f"Error al leer el archivo PDF: {str(e)}")

def save_output(result: dict, source_name: str, output_dir: str = "output") -> str:
    """
    Save the analysis result to a JSON file.
    
    Args:
        result (dict): Analysis result to save
        source_name (str): Original source name (file or URL)
        output_dir (str): Directory to save output files
        
    Returns:
        str: Path to the saved file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate output filename based on source name
    input_filename = Path(source_name).stem if os.path.isfile(source_name) else source_name.replace("://", "_").replace("/", "_").replace(".", "_")
    output_file = os.path.join(output_dir, f"{input_filename}_analysis.json")
    
    # Save the result
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    return output_file

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Extract entities and relationships from text files or web pages"
    )
    
    # Modo de operación (mutuamente exclusivo entre analizar o solo resetear)
    mode_group = parser.add_mutually_exclusive_group()
    
    # Opción para resetear la base de datos solamente
    mode_group.add_argument(
        "--reset-db-only",
        action="store_true",
        help="Resetear la base de datos sin procesar ningún documento"
    )
    
    # Opción para análisis (con --file o --url)
    mode_group.add_argument(
        "--analyze",
        action="store_true",
        help="Analizar un documento o URL (debe especificar --file o --url)"
    )
    
    # Fuente de entrada (requerido si se usa --analyze)
    input_source = parser.add_mutually_exclusive_group()
    input_source.add_argument(
        "--file", 
        help="Path to the text file to analyze"
    )
    input_source.add_argument(
        "--url",
        help="URL of the web page to analyze"
    )
    input_source.add_argument(
        "--pdf",
        help="Path to the PDF file to analyze"
    )
    
    # Otras opciones
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to save the analysis results (default: output)"
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Language of the text (default: en)"
    )
    parser.add_argument(
        "--store-db",
        action="store_true",
        help="Store results in Neo4j database"
    )
    parser.add_argument(
        "--skip-file",
        action="store_true",
        help="Skip saving results to file (useful when only storing in database)"
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Resetear la base de datos antes de procesar (elimina todos los datos existentes)"
    )
    parser.add_argument(
        "--provider",
        choices=LLMConfig.get_available_providers(),
        default=AppConfig.DEFAULT_LLM_PROVIDER,
        help=f"LLM provider to use (default: {AppConfig.DEFAULT_LLM_PROVIDER})"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode to show LLM prompts and responses"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Validar argumentos
    if not args.reset_db_only:
        # Si no es reset-only, entonces se requiere analizar algo
        args.analyze = True
        if not (args.file or args.url or args.pdf):
            parser.error("Para analizar, debe especificar --file, --url o --pdf")
    
    # Validar configuración
    if not AppConfig.validate_config():
        logger.error("Error en la configuración. Revisa el archivo .env")
        sys.exit(1)
    
    # Inicializar conexión a la base de datos si se requiere
    graph_db = None
    if args.store_db or args.reset_db or args.reset_db_only:
        try:
            graph_db = EntityGraph()
            logger.info("Conectado a la base de datos Neo4j")
        except Exception as e:
            logger.error(f"Error al conectar con Neo4j: {str(e)}")
            if args.reset_db_only:
                logger.error("No se puede continuar sin conexión a la base de datos para resetear")
                sys.exit(1)
            elif input("¿Continuar sin almacenamiento en base de datos? (y/n): ").lower() != 'y':
                sys.exit(1)
    
    try:
        # Manejar reseteo de la base de datos si se solicita
        if graph_db and (args.reset_db or args.reset_db_only):
            logger.info("Reseteando la base de datos...")
            confirm = input("¿Estás seguro de que quieres resetear la base de datos? Esta acción NO se puede deshacer. [s/N]: ")
            if confirm.lower() in ['s', 'si', 'sí', 'y', 'yes']:
                if graph_db.reset_database(confirm=True):
                    logger.info("Base de datos reseteada exitosamente")
                else:
                    logger.error("No se pudo resetear completamente la base de datos")
                    if input("¿Continuar de todas formas? [s/N]: ").lower() not in ['s', 'si', 'sí', 'y', 'yes']:
                        sys.exit(1)
            else:
                logger.info("Reseteo de base de datos cancelado por el usuario")
                
        # Si solo es reseteo, terminar aquí
        if args.reset_db_only:
            logger.info("Operación de reseteo de base de datos completada")
            return
        
        # Crear instancia del extractor con el proveedor especificado
        logger.info(f"Usando proveedor de LLM: {args.provider}")
        extractor = EntityRelationshipExtractor(provider_name=args.provider, debug_mode=args.debug)
        
        # Procesar archivo, URL o PDF
        source_name = ""
        doc_title = ""
        source_url = None
        result = None
        
        if args.file:
            # Cargar desde archivo de texto
            logger.info(f"Cargando archivo: {args.file}")
            text = load_text_file(args.file)
            source_name = args.file
            doc_title = Path(args.file).stem.replace('_', ' ').title()
            logger.info("Analizando texto...")
            result = extractor.analyze_text(
                text=text,
                doc_title=doc_title,
                language=args.language
            )
        elif args.url:
            # Cargar desde URL
            logger.info(f"Obteniendo página web: {args.url}")
            text, page_title = fetch_web_content(args.url)
            source_name = args.url
            source_url = args.url
            doc_title = page_title
            logger.info("Analizando texto...")
            result = extractor.analyze_text(
                text=text,
                doc_title=doc_title,
                language=args.language
            )
        elif args.pdf:
            # Cargar desde archivo PDF
            logger.info(f"Cargando archivo PDF: {args.pdf}")
            pdf_content = load_pdf_file(args.pdf)
            source_name = args.pdf
            doc_title = Path(args.pdf).stem.replace('_', ' ').title()
            logger.info("Analizando documento PDF...")
            result = extractor.analyze_pdf(
                pdf_content=pdf_content,
                doc_title=doc_title,
                language=args.language
            )
        
        if result:
            # Guardar el resultado en archivo si no se omite
            if not args.skip_file:
                output_file = save_output(result, source_name, args.output_dir)
                logger.info(f"Resultados guardados en archivo: {output_file}")
            
            # Almacenar en Neo4j si se solicita
            if graph_db and args.store_db:
                logger.info("Almacenando resultados en base de datos Neo4j...")
                document_id = graph_db.store_analysis_results(result, source_url)
                logger.info(f"Resultados almacenados en base de datos con ID de documento: {document_id}")
            
            logger.info("¡Análisis completado!")
        else:
            logger.error("No se pudo generar ningún resultado del análisis.")
        
    except FileNotFoundError as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)
    except IOError as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)
    except ConnectionError as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Ocurrió un error inesperado: {str(e)}")
        sys.exit(1)
    finally:
        # Cerrar conexión a Neo4j si está abierta
        if graph_db:
            graph_db.close()

if __name__ == "__main__":
    main()