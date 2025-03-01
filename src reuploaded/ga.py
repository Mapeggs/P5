import copy
import heapq
import metrics
import multiprocessing.pool as mpool
import os
import random
import shutil
import time
import math

width = 200
height = 16

options = [
    "-",  # an empty space
    "X",  # a solid wall
    "?",  # a question mark block with a coin
    "M",  # a question mark block with a mushroom
    "B",  # a breakable block
    "o",  # a coin
    "|",  # a pipe segment
    "T",  # a pipe top
    "E",  # an enemy
    #"f",  # a flag, do not generate
    #"v",  # a flagpole, do not generate
    #"m"  # mario's start position, do not generate
]

# The level as a grid of tiles


class Individual_Grid(object):
    __slots__ = ["genome", "_fitness"]

    def __init__(self, genome):
        self.genome = copy.deepcopy(genome)
        self._fitness = None

    # Update this individual's estimate of its fitness.
    # This can be expensive so we do it once and then cache the result.
    def calculate_fitness(self):
        measurements = metrics.metrics(self.to_level())
        # Print out the possible measurements or look at the implementation of metrics.py for other keys:
        # print(measurements.keys())
        # Default fitness function: Just some arbitrary combination of a few criteria.  Is it good?  Who knows?
        # STUDENT Modify this, and possibly add more metrics.  You can replace this with whatever code you like.
        coefficients = dict(
            meaningfulJumpVariance=0.5,
            negativeSpace=0.6,
            pathPercentage=0.5,
            emptyPercentage=0.6,
            linearity=-0.5,
            solvability=2.0
        )
        self._fitness = sum(map(lambda m: coefficients[m] * measurements[m],
                                coefficients))
        return self

    # Return the cached fitness value or calculate it as needed.
    def fitness(self):
        if self._fitness is None:
            self.calculate_fitness()
        return self._fitness

    # Mutate a genome into a new genome.  Note that this is a _genome_, not an individual!
    def mutate(self, genome):
        # STUDENT implement a mutation operator, also consider not mutating this individual
        # STUDENT also consider weighting the different tile types so it's not uniformly random
        # STUDENT consider putting more constraints on this to prevent pipes in the air, etc
        mutation_rate = 1.0

        left = 1
        right = width - 1
        for y in range(height):
            for x in range(left, right):
                current_tile = genome[y][x]
                if current_tile == "T" or current_tile == "|" or current_tile == "f" or current_tile == "v" or current_tile == "m":
                    continue  # Skip mutation for forbidden tiles
                # 20% chance to change a block types
                elif ((current_tile == "B" or current_tile == "M" or current_tile == "?") and
                    random.random() < 0.2 * mutation_rate):
                    genome[y][x] = random.choices(["B", "?", "M"], weights=[0.7, 0.2, 0.1])[0]
                # 3% chance to add a coin or enemy above a blocks
                elif current_tile == "-" and random.random() < 0.03 * mutation_rate:
                    if y + 1 < height and (genome[y + 1][x] == "B" or genome[y + 1][x] == "X"):
                        genome[y][x] = random.choices(["o", "E"], weights=[0.7, 0.3])[0]
                # 1% chance to remove a coin or enemy
                elif (current_tile == "o" or current_tile == "E") and random.random() < 0.01 * mutation_rate:
                    genome[y][x] = "-"
                # 1% chance to mutate an empty space above height 4 and empty space 2 tiles below to a breakable block
                elif (current_tile == "-" and
                    random.random() < (0.01 - (0.01 * (height - y) / height)) * mutation_rate and 
                    height - y > 4 and
                    all(genome[dy][x] == "-" for dy in range(y+1, y+2)) and
                    all(genome[dy][x+1] == "-" for dy in range(y+1, y+2)) and
                    all(genome[dy][x-1] == "-" for dy in range(y+1, y+2))):

                    genome[y][x] = "B"

                elif (current_tile == "-" and
                    random.random() < 0.01 * mutation_rate and 
                    (genome[y][x+1] == "B" or genome[y][x-1] == "B") and
                    all(genome[dy][x] == "-" for dy in range(y+1, y+2)) and
                    all(genome[dy][x+1] == "-" for dy in range(y+1, y+2)) and
                    all(genome[dy][x-1] == "-" for dy in range(y+1, y+2))):

                    genome[y][x] = "B"
                # 1% chance (increasing to 5% with height) to mutate an remove breakable block
                if current_tile == "B" and random.random() < (0.01 + (0.04 * (height - y) / height)) * mutation_rate:
                    genome[y][x] = "-"

                # 2% chance to change X to empty space if there is nothing above
                elif current_tile == "X" and genome[y - 1][x] == "-" and random.random() < 0.02 * mutation_rate:
                    genome[y][x] = "-"
                    if (random.random() < 0.25 * mutation_rate and
                        genome[y][x-1] == "X" and
                        genome[y][x+1] == "X" and
                        x-1 > 0 and
                        x+1 < width - 1):
                        genome[y][x-1] = "-"
                        genome[y][x+1] = "-"

        return genome

    # Create zero or more children from self and other
    def generate_children(self, other):
        new_genome = copy.deepcopy(self.genome)
        # Leaving first and last columns alone...
        # do crossover with other
        left = 1
        right = width - 1
        for y in range(height - 1, 0, -1):
            for x in range(left, right):
                # STUDENT Which one should you take?  Self, or other?  Why?
                # STUDENT consider putting more constraints on this to prevent pipes in the air, etc
                threshold = 5
                pipeMax = 10

                # 5% chance to add a pipe
                if height - y < threshold and random.random() < 0.05:
                    # take highest fitness pipe or 20% chance to take lower fitness a pipe
                    if (self.genome[y][x] == "T" and
                        (self.fitness() < other.fitness() or random.random() < 0.20) and
                        all(new_genome[dy][x] == "-" for dy in range(y+2, height - 1)) and
                        all(new_genome[dy][x + 1] == "-" for dy in range(y+2, height - 1)) and
                        all(new_genome[dy][x - 1] == "-" for dy in range(y+2, height - 1)) and
                        sum(row.count("T") for row in new_genome) < pipeMax):

                        # add whole pipe
                        new_genome[y][x] = "T"
                        for dy in range(y+1, height - 1):
                            new_genome[dy][x] = "|"  

                    # take highest fitness pipe
                    elif (other.genome[y][x] == "T" and
                        other.fitness() < self.fitness() and
                        all(new_genome[dy][x] == "-" for dy in range(y+2, height - 1)) and
                        all(new_genome[dy][x + 1] == "-" for dy in range(y+2, height - 1)) and
                        all(new_genome[dy][x - 1] == "-" for dy in range(y+2, height - 1)) and
                        sum(row.count("T") for row in new_genome) < pipeMax):

                        # add whole pipe
                        new_genome[y][x] = "T"
                        for dy in range(y+1, height - 1):
                            new_genome[dy][x] = "|"  

                # if equal to threshold hight and a parent has a brick, add a brick 
                if height - y == threshold and (self.genome[y][x] == "B" or other.genome[y][x] == "B"):
                    count_B = sum(1 for row in new_genome if row[x] == "B")
                    # 15% have brick on tile, but less likely as number of bricks increases
                    if random.random() < 0.15 - (0.15 * (2 * count_B / width)):
                        new_genome[y][x] = "B"
                        if random.random() < 0.3:  # 30% chance to place another block
                            offset_x = random.choice([-1, 1])  # left, or right
                            offset_y = random.randint(3, 5)  # between 3 and 5 blocks higher
                            new_x = clip(left, x + offset_x, right - 1)
                            new_y = clip(0, y - offset_y, height - 1)
                            if new_genome[new_y][new_x] == "-":
                                new_genome[new_y][new_x] = "B"
                        elif random.random() < 0.3:  # 30% chance to place block to either side
                            offset_x = random.choice([-1, 1])  # left, or right
                            new_x = clip(left, x + offset_x, right - 1)
                            if new_genome[y][new_x] == "-":
                                new_genome[y][new_x] = "B"

                # don't change the forbidden tiles
                if self.genome[y][x] == "v" or self.genome[y][x] == "f" or self.genome[y][x] == "m":
                    new_genome[y][x] = self.genome[y][x]
                    
        new_genome = self.mutate(new_genome)

        # do mutation; note we're returning a one-element tuple here
        return (Individual_Grid(new_genome),)

    # Turn the genome into a level string (easy for this genome)
    def to_level(self):
        return self.genome

    # These both start with every floor tile filled with Xs
    # STUDENT Feel free to change these
    @classmethod
    def empty_individual(cls):
        g = [["-" for col in range(width)] for row in range(height)]
        g[15][:] = ["X"] * width
        g[14][0] = "m"
        g[7][-2] = "v"
        for col in range(8, 14):
            g[col][-2] = "f"
        for col in range(14, 16):
            g[col][-2] = "X"
        return cls(g)

    @classmethod
    def random_individual(cls):
        # STUDENT consider putting more constraints on this to prevent pipes in the air, etc
        # STUDENT also consider weighting the different tile types so it's not 
        g = [random.choices(options, k=width) for row in range(height)]
        g[15][:] = ["X"] * width
        g[14][0] = "m"
        g[7][-2] = "v"
        g[8:14][-2] = ["f"] * 6
        g[14:16][-2] = ["X", "X"]
        return cls(g)


def offset_by_upto(val, variance, min=None, max=None):
    val += random.normalvariate(0, variance**0.5)
    if min is not None and val < min:
        val = min
    if max is not None and val > max:
        val = max
    return int(val)


def clip(lo, val, hi):
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val

# Inspired by https://www.researchgate.net/profile/Philippe_Pasquier/publication/220867545_Towards_a_Generic_Framework_for_Automated_Video_Game_Level_Creation/links/0912f510ac2bed57d1000000.pdf


class Individual_DE(object):
    # Calculating the level isn't cheap either so we cache it too.
    __slots__ = ["genome", "_fitness", "_level"]

    # Genome is a heapq of design elements sorted by X, then type, then other parameters
    def __init__(self, genome):
        self.genome = list(genome)
        heapq.heapify(self.genome)
        self._fitness = None
        self._level = None

    # Calculate and cache fitness
    def calculate_fitness(self):
        measurements = metrics.metrics(self.to_level())
        # Default fitness function: Just some arbitrary combination of a few criteria.  Is it good?  Who knows?
        # STUDENT Add more metrics?
        # STUDENT Improve this with any code you like
        coefficients = dict(
            meaningfulJumpVariance=0.5,
            negativeSpace=0.6,
            pathPercentage=0.5,
            emptyPercentage=0.6,
            linearity=-0.5,
            solvability=2.0
        )
        penalties = 0
        # STUDENT For example, too many stairs are unaesthetic.  Let's penalize that
        if len(list(filter(lambda de: de[1] == "6_stairs", self.genome))) > 5:
            penalties -= 2
        # STUDENT If you go for the FI-2POP extra credit, you can put constraint calculation in here too and cache it in a new entry in __slots__.
        self._fitness = sum(map(lambda m: coefficients[m] * measurements[m],
                                coefficients)) + penalties
        return self

    def fitness(self):
        if self._fitness is None:
            self.calculate_fitness()
        return self._fitness

    def mutate(self, new_genome):
        # STUDENT How does this work?  Explain it in your writeup.
        # STUDENT consider putting more constraints on this, to prevent generating weird things
        if random.random() < 0.1 and len(new_genome) > 0:
            to_change = random.randint(0, len(new_genome) - 1)
            de = new_genome[to_change]
            new_de = de
            x = de[0]
            de_type = de[1]
            choice = random.random()

            # Mutating blocks (breakable and question blocks)
            if de_type == "4_block":
                y = de[2]
                breakable = de[3]
                if choice < 0.3: #orginal 0.33
                    x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                elif choice < 0.6: #orginal 0.6
                    y = offset_by_upto(y, 2, min=5, max=height - 6)
                else:
                    breakable = not breakable
                # Ensure"X" blocks are only at ground level or part of stairs 
                if random.random() < 0.5:
                    x += random.choice([-1, 1])
                new_de = (x, de_type, y, breakable)

            # Mutating question mark blocks (power-ups)                   
            elif de_type == "5_qblock":
                y = de[2]
                has_powerup = de[3]  # boolean
                if choice < 0.4:
                    x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                elif choice < 0.7:
                    y = offset_by_upto(y, height / 5, min=2, max=height - 6)
                else:
                    has_powerup = not has_powerup
                new_de = (x, de_type, y, has_powerup)

            # Mutating coins (ensuring they don’t go underground)
            elif de_type == "3_coin":
                y = de[2]
                if choice < 0.5:
                    x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                else:
                    y = offset_by_upto(y, height / 2, min=2, max=height - 3)
                new_de = (x, de_type, y)
            
             # Mutating pipes (keeping them on the ground)   
            elif de_type == "7_pipe":
                h = de[2]
                if choice < 0.5:
                    x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                else:
                    h = offset_by_upto(h, 1, min=2, max=4) # Keep pipes at reasonable height
                new_de = (x, de_type, h)

            # Mutating holes (gaps in the ground)    
            elif de_type == "0_hole":
                w = de[2]
                if choice < 0.5:
                    x = offset_by_upto(x, width / 3, min=1, max=width - 2)
                else:
                     w = offset_by_upto(w, 1, min=1, max=3)
                #Ensure gap don't clusters too much
                if random.random() < 0.5:
                    x += random.choice([-3,3])#offset holes slightly
                new_de = (x, de_type, w)

            # Mutating stairs (adjust height, but limit extreme cases)
            elif de_type == "6_stairs":
                h = de[2]
                dx = de[3]   # Direction (-1 for left, +1 for right)
                if choice < 0.3:
                    x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                elif choice < 0.6:
                    h = offset_by_upto(h, 3, min=3, max=height - 4)
                else:
                    dx = -dx
                new_de = (x, de_type, h, dx)
            
            # Mutating platforms (ensuring they remain useful)
            elif de_type == "1_platform":
                w = de[2]
                y = de[3]
                madeof = de[4]  # from "?", "X", "B"
                if choice < 0.25:
                    x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                elif choice < 0.5:
                    w = offset_by_upto(w, 8, min=2, max=width // 6)
                elif choice < 0.75:
                    y = offset_by_upto(y, height / 3, min=3, max=height - 4)
                else:
                    madeof = random.choice(["?", "X", "B"])
                new_de = (x, de_type, w, y, madeof)
            
            elif de_type == "2_enemy":
                x = offset_by_upto(x, width / 8, min=1, max=width - 2)
                new_de = (x, de_type)
            new_genome.pop(to_change)
            heapq.heappush(new_genome, new_de)
        return new_genome

    def generate_children(self, other):
        # STUDENT How does this work?  Explain it in your writeup.
        if len(self.genome) == 0 or len(other.genome) == 0:
            return (Individual_DE.random_individual(),)  # Replace empty individuals

        pa = random.randint(0, len(self.genome) - 1)
        pb = random.randint(0, len(other.genome) - 1)
        a_part = self.genome[:pa] if len(self.genome) > 0 else []
        b_part = other.genome[pb:] if len(other.genome) > 0 else []
        ga = a_part + b_part
        b_part = other.genome[:pb] if len(other.genome) > 0 else []
        a_part = self.genome[pa:] if len(self.genome) > 0 else []
        gb = b_part + a_part
        # do mutation
        return Individual_DE(self.mutate(ga)), Individual_DE(self.mutate(gb))

    # Apply the DEs to a base level.
    def to_level(self):
        if self._level is None:
            base = Individual_Grid.empty_individual().to_level()
            for de in sorted(self.genome, key=lambda de: (de[1], de[0], de)):
                # de: x, type, ...
                x = de[0]
                de_type = de[1]
                if de_type == "4_block":
                    y = de[2]
                    breakable = de[3]
                    base[y][x] = "B" if breakable else "X"
                elif de_type == "5_qblock":
                    y = de[2]
                    has_powerup = de[3]  # boolean
                    base[y][x] = "M" if has_powerup else "?"
                elif de_type == "3_coin":
                    y = de[2]
                    base[y][x] = "o"
                elif de_type == "7_pipe":
                    h = de[2]
                    base[height - h - 1][x] = "T"
                    for y in range(height - h, height):
                        base[y][x] = "|"
                elif de_type == "0_hole":
                    w = de[2]
                    for x2 in range(w):
                        base[height - 1][clip(1, x + x2, width - 2)] = "-"
                elif de_type == "6_stairs":
                    h = de[2]
                    dx = de[3]  # -1 or 1
                    for x2 in range(1, h + 1):
                        for y in range(x2 if dx == 1 else h - x2):
                            base[clip(0, height - y - 1, height - 1)][clip(1, x + x2, width - 2)] = "X"
                elif de_type == "1_platform":
                    w = de[2]
                    h = de[3]
                    madeof = de[4]  # from "?", "X", "B"
                    for x2 in range(w):
                        base[clip(0, height - h - 1, height - 1)][clip(1, x + x2, width - 2)] = madeof
                elif de_type == "2_enemy":
                    base[height - 2][x] = "E"
            self._level = base
        return self._level

    @classmethod
    def empty_individual(_cls):
        # STUDENT Maybe enhance this
        g = []
        return Individual_DE(g)

    @classmethod
    def random_individual(_cls):
        # STUDENT Maybe enhance this
        elt_count = random.randint(20, 60)
        g = []
    
        for _ in range(elt_count):
            element = random.choice([
                (random.randint(1, width - 2), "0_hole", random.randint(1, 3)),
                (random.randint(1, width - 2), "1_platform", random.randint(2, 6), random.randint(0, height - 4), random.choice(["?", "X", "B"])),
                (random.randint(1, width - 2), "2_enemy"),
                (random.randint(1, width - 2), "3_coin", random.randint(4, height - 4)),
                (random.randint(1, width - 2), "4_block", random.randint(4, height - 5), True),
                (random.randint(1, width - 2), "5_qblock", random.randint(4, height - 5), random.choice([True, False])),
                (random.randint(1, width - 2), "6_stairs", random.randint(3, 6), random.choice([-1, 1])), 
                (random.randint(1, width - 2), "7_pipe", random.randint(1, 4))  # Keep pipe height in check
            ])
            g.append(element)
    
        return Individual_DE(g)


Individual = Individual_DE


def generate_successors(population):
    results = []
    # STUDENT Design and implement this
    # Hint: Call generate_children() on some individuals and fill up results.
    valid_population = [ind for ind in population if len(ind.genome) > 0]
    # If too few valid individuals, regenerate some random ones
    while len(valid_population) < len(population) // 2:
        valid_population.append(Individual_DE.random_individual())

    # Generate children from the top individuals
    num_parents = len(population) // 2
    for i in range(num_parents - int(num_parents * 0.1)):
        parent1 = population[i]
        parent2 = population[num_parents + i]
        children = parent1.generate_children(parent2)
        results.extend(children)

    # Roulette wheel selection
    total_fitness = sum(ind.fitness() for ind in population)
    if total_fitness > 0:
        selection_probs = [ind.fitness() / total_fitness for ind in population]
        selected_indices = random.choices(range(len(population)), weights=selection_probs, k=len(population) - len(results))
        for i in selected_indices:
            parent1 = population[i]
            parent2 = random.choice(population)
            children = parent1.generate_children(parent2)
            results.extend(children)
    
    # Ensure the results length is equal to the population length
    while len(results) < len(population):
        parent1 = random.choice(population[:num_parents])
        parent2 = random.choice(population[:num_parents])
        children = parent1.generate_children(parent2)
        results.extend(children)
    
    results = results[:len(population)]

    return results


def ga():
    # STUDENT Feel free to play with this parameter
    pop_limit = 480
    # Code to parallelize some computations
    batches = os.cpu_count()
    if pop_limit % batches != 0:
        print("It's ideal if pop_limit divides evenly into " + str(batches) + " batches.")
    batch_size = int(math.ceil(pop_limit / batches))
    with mpool.Pool(processes=os.cpu_count()) as pool:
        init_time = time.time()
        # STUDENT (Optional) change population initialization
        population = [Individual.random_individual() if random.random() < 0.9
                      else Individual.empty_individual()
                      for _g in range(pop_limit)]
        # But leave this line alone; we have to reassign to population because we get a new population that has more cached stuff in it.
        population = pool.map(Individual.calculate_fitness,
                              population,
                              batch_size)
        init_done = time.time()
        print("Created and calculated initial population statistics in:", init_done - init_time, "seconds")
        generation = 0
        start = time.time()
        now = start
        print("Use ctrl-c to terminate this loop manually.")
        try:
            while True:
                now = time.time()
                # Print out statistics
                if generation > 0:
                    best = max(population, key=Individual.fitness)
                    print("Generation:", str(generation))
                    print("Max fitness:", str(best.fitness()))
                    print("Average generation time:", (now - start) / generation)
                    print("Net time:", now - start)
                    with open("levels/last.txt", 'w+') as f:
                        for row in best.to_level():
                            f.write("".join(row) + "\n")
                generation += 1
                # STUDENT Determine stopping condition
                stop_condition = generation > 6
                if stop_condition:
                    break
                # STUDENT Also consider using FI-2POP as in the Sorenson & Pasquier paper
                gentime = time.time()
                next_population = generate_successors(population)
                gendone = time.time()
                print("Generated successors in:", gendone - gentime, "seconds")
                # Calculate fitness in batches in parallel
                next_population = pool.map(Individual.calculate_fitness,
                                           next_population,
                                           batch_size)
                popdone = time.time()
                print("Calculated fitnesses in:", popdone - gendone, "seconds")
                population = next_population
        except KeyboardInterrupt:
            pass
    return population


if __name__ == "__main__":
    final_gen = sorted(ga(), key=Individual.fitness, reverse=True)
    best = final_gen[0]
    print("Best fitness: " + str(best.fitness()))
    now = time.strftime("%m_%d_%H_%M_%S")
    # STUDENT You can change this if you want to blast out the whole generation, or ten random samples, or...
    for k in range(0, 10):
        with open("levels/" + now + "_" + str(k) + ".txt", 'w') as f:
            for row in final_gen[k].to_level():
                f.write("".join(row) + "\n")
