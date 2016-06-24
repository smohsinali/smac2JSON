from argparse import ArgumentParser, FileType

import pcs
import pjson

__authors__ = ["Katharina Eggensperger", "Matthias Feurer", "Moshin"]
__contact__ = "automl.org"


def main():
    prog = "python convert.py"
    description = "Convert SMAC parameters file to JSON"

    parser = ArgumentParser(description=description, prog=prog)
    parser.add_argument('input_file', nargs='?', type=FileType('r'))
    parser.add_argument("-s", "--save", dest="save", metavar="destination",
                        default="", help="Where to save the new searchspace?")

    args, unknown = parser.parse_known_args()

    # Unifying strings

    if args.input_file is None:
        raise ValueError("No input file given")

    # First read searchspace
    print("Reading searchspace...")
    searchspace = pcs.read(args.input_file)
    print("...done. Found %d params" % len(searchspace._hyperparameters))

    pjson.write(searchspace)

if __name__ == "__main__":
    main()