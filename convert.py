from argparse import ArgumentParser, FileType

import pcs
import json

__authors__ = ["Katharina Eggensperger", "Matthias Feurer", "Moshin"]
__contact__ = "automl.org"


def main():
    # python convert.py --from SMAC --to TPE -f space.any -s space.else
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

    new_space = json.write(searchspace)

    # No write it
    if args.save != "":
        output_fh = open(args.save, 'w')
        output_fh.write(new_space)
        output_fh.close()
    else:
        print(new_space)

if __name__ == "__main__":
    main()